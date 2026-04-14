# *******************************************************************************
# Copyright (c) 2025-2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************
import logging
import subprocess
import io
import os
import shlex
import tarfile
import threading
import time
import docker as pypi_docker
import pytest

from score.itf.core.com.ssh import Ssh
from score.itf.core.process.async_process import AsyncProcess

from score.itf.plugins.core import determine_target_scope
from score.itf.plugins.core import Target


logger = logging.getLogger(__name__)

# Default timeout (seconds) for Docker client operations.
DOCKER_CLIENT_TIMEOUT = 180


def pytest_addoption(parser):
    parser.addoption(
        "--docker-image",
        action="store",
        required=True,
        help="Docker image to run tests against.",
    )
    parser.addoption(
        "--docker-image-bootstrap",
        action="store",
        required=False,
        help="Docker image bootstrap command, that will be executed before referencing the container.",
    )


class DockerAsyncProcess(AsyncProcess):
    """Handle for a non-blocking command execution inside a Docker container."""

    def __init__(self, container, client, exec_id, pid, output_thread, output_lines):
        self._container = container
        self._client = client
        self.exec_id = exec_id
        self._pid = pid
        self._output_thread = output_thread
        self._output_lines = output_lines
        self._logger = logging.getLogger(f"async_exec.{pid}")

    def pid(self) -> int:
        """Return the PID of the running command."""
        return self._pid

    def is_running(self) -> bool:
        """Return *True* if the command is still executing."""
        return self._client.api.exec_inspect(self.exec_id)["Running"]

    def get_exit_code(self) -> int:
        """Return the exit code of the finished command."""
        return self._client.api.exec_inspect(self.exec_id)["ExitCode"]

    def wait(self, timeout_s: float = 15) -> int:
        """Block until the command finishes or *timeout_s* elapses.

        :param timeout_s: maximum seconds to wait.
        :return: exit code of the command.
        :raises RuntimeError: on timeout.
        """
        start_time = time.time()
        while self.is_running():
            if time.time() - start_time > timeout_s:
                raise RuntimeError(
                    f"Waiting for process with PID [{self._pid}] to terminate timed out after {timeout_s} seconds"
                )
            time.sleep(0.1)
        self._output_thread.join()
        return self.get_exit_code()

    def stop(self) -> int:
        """Terminate the running command, escalating to SIGKILL if needed.

        :return: exit code of the stopped command.
        """
        self._terminate()
        for _ in range(5):
            time.sleep(1)
            if not self.is_running():
                break
        if self.is_running():
            self._logger.error(f"Process with PID [{self._pid}] did not terminate properly, sending SIGKILL.")
            self._kill()
            self.wait()
        self._output_thread.join()
        return self.get_exit_code()

    def _terminate(self):
        self._container.exec_run(f"kill {self._pid}")

    def _kill(self):
        self._container.exec_run(f"kill -9 {self._pid}")

    def get_output(self) -> str:
        """Return the captured stdout of the command."""
        return "\n".join(self._output_lines) + ("\n" if self._output_lines else "")


class DockerTarget(Target):
    def __init__(self, container):
        super().__init__()
        self.container = container
        self._client = pypi_docker.from_env(timeout=DOCKER_CLIENT_TIMEOUT)

    def __getattr__(self, name):
        return getattr(self.container, name)

    def execute(self, command: str):
        return self.container.exec_run(f"/bin/sh -c {shlex.quote(command)}")

    def execute_async(self, binary_path, args=None, cwd="/", **kwargs) -> DockerAsyncProcess:
        """Start a binary without blocking and return a :class:`DockerAsyncProcess` handle.

        The command is wrapped in a shell that prints its PID first,
        then runs the real command so that the PID can be used for later signal delivery.

        :param binary_path: path to the binary to execute.
        :param args: list of string arguments for the binary.
        :param cwd: working directory inside the container.
        :return: a :class:`DockerAsyncProcess` instance for lifecycle management.
        """
        if args is None:
            args = []
        command = f"{binary_path} {' '.join(shlex.quote(a) for a in args)}"
        # Use a list form so Docker calls execve directly — no outer shell
        # quoting to worry about.  The first bash prints its PID and then
        # exec's a second bash that runs the (possibly compound) command.
        # shlex.quote() safely wraps the user command for the inner -c arg.
        exec_instance = self._client.api.exec_create(
            self.container.id,
            cmd=[
                "/bin/bash",
                "-c",
                f"echo $$; exec /bin/bash -c {shlex.quote(command)}",
            ],
            workdir=cwd,
        )
        exec_id = exec_instance["Id"]
        # demux=True delivers stdout/stderr as separate (bytes|None, bytes|None)
        # tuples, preventing early stderr from the child from masking the PID.
        stream = self._client.api.exec_start(exec_id, stream=True, demux=True)

        cmd_logger = logging.getLogger(os.path.basename(command.split()[0]))
        output_lines = []

        def _process_text(text):
            for line in text.strip().split("\n"):
                if line:
                    cmd_logger.info(line)
                    output_lines.append(line)

        pid = None
        for stdout_chunk, stderr_chunk in stream:
            if stderr_chunk:
                _process_text(stderr_chunk.decode())
            if stdout_chunk:
                pid_line, _, remainder = stdout_chunk.decode().partition("\n")
                pid = int(pid_line.strip())
                if remainder.strip():
                    _process_text(remainder)
                break

        if pid is None:
            raise RuntimeError(f"Failed to extract PID from stdout for '{command}'")

        def _async_log(log_stream):
            for stdout_chunk, stderr_chunk in log_stream:
                if stdout_chunk:
                    _process_text(stdout_chunk.decode())
                if stderr_chunk:
                    _process_text(stderr_chunk.decode())

        output_thread = threading.Thread(target=_async_log, args=(stream,), daemon=True)
        output_thread.start()

        return DockerAsyncProcess(self.container, self._client, exec_id, pid, output_thread, output_lines)

    def upload(self, local_path: str, remote_path: str) -> None:
        if not os.path.isfile(local_path):
            raise FileNotFoundError(local_path)

        remote_dir = os.path.dirname(remote_path) or "/"
        remote_name = os.path.basename(remote_path)

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w", dereference=True) as tar:
            tar.add(local_path, arcname=remote_name)
        tar_stream.seek(0)

        ok = self.container.put_archive(remote_dir, tar_stream.getvalue())
        if not ok:
            raise RuntimeError(f"Failed to upload '{local_path}' to '{remote_path}'")

    def download(self, remote_path: str, local_path: str) -> None:
        stream, _ = self.container.get_archive(remote_path)
        tar_bytes = b"".join(stream)

        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tar:
            members = tar.getmembers()
            if not members:
                raise FileNotFoundError(remote_path)

            member = members[0]
            extracted = tar.extractfile(member)
            if extracted is None:
                raise FileNotFoundError(remote_path)
            with open(local_path, "wb") as f:
                f.write(extracted.read())

    def restart(self) -> None:
        self.container.restart()

    def get_ip(self):
        self.container.reload()
        return self.container.attrs["NetworkSettings"]["Networks"]["bridge"]["IPAddress"]

    def get_gateway(self):
        self.container.reload()
        return self.container.attrs["NetworkSettings"]["Networks"]["bridge"]["Gateway"]

    def ssh(self, username="score", password="score", port=2222):
        return Ssh(target_ip=self.get_ip(), port=port, username=username, password=password)


@pytest.fixture(scope=determine_target_scope)
def docker_configuration():
    """
    Fixture that provides a customization point for Docker configuration in tests.

    This fixture allows tests to override and customize Docker settings by providing
    a dictionary of configuration parameters. Tests can use this fixture to inject
    custom Docker configuration values as needed for their specific test scenarios.

    Returns:
        dict: An empty dictionary that can be populated with custom Docker configuration
            parameters by tests or through pytest fixtures/parametrization.

    Scope:
        The fixture scope is determined dynamically based on the target scope.
    """
    return {}


@pytest.fixture(scope=determine_target_scope)
def _docker_configuration(docker_configuration):
    configuration = {
        "environment": {},
        "command": "sleep infinity",
        "init": True,
        "shm_size": "2G",
        "volumes": {},
    }
    merged_configuration = {**configuration, **docker_configuration}

    return merged_configuration


@pytest.fixture(scope=determine_target_scope)
def target_init(request, _docker_configuration):
    print(_docker_configuration)

    docker_image_bootstrap = request.config.getoption("docker_image_bootstrap")
    if docker_image_bootstrap:
        logger.info(f"Executing custom image bootstrap command: {docker_image_bootstrap}")
        subprocess.run([docker_image_bootstrap], check=True)

    docker_image = request.config.getoption("docker_image")
    client = pypi_docker.from_env(timeout=DOCKER_CLIENT_TIMEOUT)
    container = client.containers.run(
        docker_image,
        _docker_configuration["command"],
        detach=True,
        auto_remove=False,
        init=_docker_configuration["init"],
        environment=_docker_configuration["environment"],
        volumes=_docker_configuration["volumes"],
        shm_size=_docker_configuration["shm_size"],
    )
    try:
        yield DockerTarget(container)
    finally:
        try:
            container.stop(timeout=1)
        finally:
            # Ensure restart() doesn't accidentally delete the container mid-test.
            container.remove(force=True)
