# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
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
"""Asynchronous processes through the Docker exec API (`docker.process`)."""

from __future__ import annotations

import logging
import os
import shlex
import threading
import time

from score.itf.core.process import AsyncProcess

from .command import Platform


class DockerAsyncProcess(AsyncProcess):
    """A command started with the Docker exec API; signals go by the PID the wrapper shell printed."""

    def __init__(self, platform: Platform, exec_id: str, pid: int, output_thread, output: list[str]):
        self._platform = platform
        self.exec_id = exec_id
        self._pid = pid
        self._output_thread = output_thread
        self._output = output
        self._logger = logging.getLogger(f"async_exec.{pid}")

    def _inspect(self) -> dict:
        return self._platform.client().api.exec_inspect(self.exec_id)

    def pid(self) -> int:
        return self._pid

    def is_running(self) -> bool:
        return self._inspect()["Running"]

    def get_exit_code(self) -> int:
        return self._inspect()["ExitCode"]

    def wait(self, timeout_s: float = 15) -> int:
        deadline = time.monotonic() + timeout_s
        while self.is_running():
            if time.monotonic() > deadline:
                raise RuntimeError(
                    f"Waiting for process with PID [{self._pid}] to terminate timed out after {timeout_s} seconds"
                )
            time.sleep(0.1)
        self._output_thread.join()
        return self.get_exit_code()

    def stop(self) -> int:
        self._platform.container.exec_run(["/bin/sh", "-c", f"kill {self._pid}"])
        for _ in range(5):
            time.sleep(1)
            if not self.is_running():
                break
        if self.is_running():
            self._logger.error("Process with PID [%s] did not terminate properly, sending SIGKILL.", self._pid)
            self._platform.container.exec_run(["/bin/sh", "-c", f"kill -9 {self._pid}"])
            self.wait()
        self._output_thread.join()
        return self.get_exit_code()

    def get_output(self) -> str:
        return "\n".join(self._output) + ("\n" if self._output else "")


class DockerProcess:
    """`process` through the Docker exec API."""

    def __init__(self, platform: Platform):
        self.platform = platform

    def spawn(self, binary_path: str, args: list[str] | None = None, cwd: str = "/", **kwargs) -> DockerAsyncProcess:
        command = " ".join([binary_path, *(shlex.quote(a) for a in (args or []))])
        api = self.platform.client().api
        # The outer shell prints its PID, then execs a shell running the (possibly compound) command.
        # bash when the image has it: it execs a simple command in place, so the PID is the
        # program's own and signals reach it; dash would keep a shell in between.
        quoted = shlex.quote(command)
        wrapper = (
            f"echo $$; if command -v bash >/dev/null 2>&1; then exec bash -c {quoted}; "
            f"else exec /bin/sh -c {quoted}; fi"
        )
        exec_id = api.exec_create(self.platform.container.id, workdir=cwd, cmd=["/bin/sh", "-c", wrapper])["Id"]
        stream = api.exec_start(exec_id, stream=True, demux=True)

        cmd_logger = logging.getLogger(os.path.basename(binary_path.split()[0]))
        output: list[str] = []

        def record(text: str) -> None:
            for line in text.strip().split("\n"):
                if line:
                    cmd_logger.info(line)
                    output.append(line)

        pid = None
        for stdout_chunk, stderr_chunk in stream:
            if stderr_chunk:
                record(stderr_chunk.decode(errors="replace"))
            if stdout_chunk:
                pid_line, _, rest = stdout_chunk.decode(errors="replace").partition("\n")
                pid = int(pid_line.strip())
                if rest.strip():
                    record(rest)
                break
        if pid is None:
            raise RuntimeError(f"Failed to extract PID from stdout for '{command}'")

        def pump() -> None:
            for stdout_chunk, stderr_chunk in stream:
                if stdout_chunk:
                    record(stdout_chunk.decode(errors="replace"))
                if stderr_chunk:
                    record(stderr_chunk.decode(errors="replace"))

        thread = threading.Thread(target=pump, daemon=True)
        thread.start()
        return DockerAsyncProcess(self.platform, exec_id, pid, thread, output)

    def wrap_exec(self, *args, **kwargs):
        from score.itf.core.process import WrappedProcess

        return WrappedProcess(self, *args, **kwargs)
