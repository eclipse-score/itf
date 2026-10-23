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
"""ITF plugin for a physical (bare-metal) SSH target.

Provides the ``target`` fixture pointing at any host reachable over SSH.
Credentials are passed at runtime via ``--hw-user`` / ``--hw-password`` so
that no secrets are stored in the repository.

Usage (plain pytest)::

    python main.py \\
        -p score.itf.plugins.core -p score.itf.plugins.hw_ssh \\
        --hw-host=192.168.0.175 --hw-user=pi --hw-password=<pass> \\
        test/test_hw.py -s

Usage (Bazel)::

    bazel test //test:test_hw \\
        --test_arg=--hw-user=pi --test_arg=--hw-password=<pass> \\
        --test_output=all
"""
import logging
from typing import List, Optional

import pytest

from score.itf.core.com.ssh import Ssh
from score.itf.core.com.sftp import Sftp
from score.itf.core.com.ping import ping
from score.itf.core.process.async_process import AsyncProcess

from score.itf.plugins.core import Target, determine_target_scope


logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--hw-host",
        action="store",
        default="192.168.0.175",
        help="IP address or hostname of the hardware target (default: 192.168.0.175).",
    )
    parser.addoption(
        "--hw-port",
        action="store",
        type=int,
        default=22,
        help="SSH port of the hardware target (default: 22).",
    )
    parser.addoption(
        "--hw-user",
        action="store",
        required=True,
        help="SSH username for the hardware target.",
    )
    parser.addoption(
        "--hw-password",
        action="store",
        required=True,
        help="SSH password for the hardware target.",
    )


class HwTarget(Target):
    """Target implementation for a physical host reachable over SSH/SFTP."""

    def __init__(self, host: str, port: int, username: str, password: str):
        super().__init__(capabilities={"ssh", "sftp"})
        self._host = host
        self._port = port
        self._username = username
        self._password = password

    def ssh(
        self,
        timeout: int = 15,
        port: Optional[int] = None,
        n_retries: int = 5,
        retry_interval: int = 2,
        username: Optional[str] = None,
        password: Optional[str] = None,
        pkey_path: str = "",
    ) -> Ssh:
        """Return an :class:`Ssh` context manager connected to the target.

        Falls back to the credentials supplied at plugin init when *username*
        or *password* are not given, so callers can override per-call without
        losing the defaults.
        """
        return Ssh(
            target_ip=self._host,
            port=port if port is not None else self._port,
            timeout=timeout,
            n_retries=n_retries,
            retry_interval=retry_interval,
            pkey_path=pkey_path,
            username=username if username is not None else self._username,
            password=password if password is not None else self._password,
        )

    def sftp(self, ssh_connection: Optional[Ssh] = None) -> Sftp:
        """Return an :class:`Sftp` context manager for the target.

        When *ssh_connection* is not given a new SSH connection is opened using
        the credentials stored on this target.
        """
        return Sftp(
            ssh_connection,  # type: ignore[arg-type]  # Sftp handles None at runtime
            self._host,
            self._port,
            username=self._username,
            password=self._password,
        )

    def execute(self, command: str):
        """Run *command* on the target and return ``(exit_code, output_bytes)``."""
        timeout = 30
        max_exec_time = 180
        with self.ssh(timeout=timeout) as ssh:
            exit_code, output_lines, _ = ssh.execute_command_output(
                command,
                timeout=timeout,
                max_exec_time=max_exec_time,
                verbose=True,
            )
        return exit_code, "".join(output_lines).encode()

    def upload(self, local_path: str, remote_path: str) -> None:
        with self.sftp() as sftp:
            sftp.upload(local_path, remote_path)

    def download(self, remote_path: str, local_path: str) -> None:
        with self.sftp() as sftp:
            sftp.download(remote_path, local_path)

    def ping(self, timeout: int, interval: int = 1) -> bool:
        """Return ``True`` when the target responds to ICMP ping within *timeout* seconds."""
        return ping(address=self._host, timeout=timeout, interval=interval)

    def execute_async(
        self,
        binary_path: str,
        args: Optional[List[str]] = None,
        cwd: str = "/",
    ) -> AsyncProcess:
        raise NotImplementedError(
            "execute_async is not implemented for HwTarget. "
            "Port QemuTarget.execute_async from score/itf/plugins/qemu/qemu_target.py if needed."
        )

    def restart(self) -> None:
        """Reboot the target over SSH.

        Requires the SSH user to have permission to run ``reboot``.
        The SSH connection will drop immediately; the caller is responsible
        for waiting until the host is back up.
        """
        self.execute("reboot")


@pytest.fixture(scope=determine_target_scope)
def target_init(request):
    host = request.config.getoption("hw_host")
    port = request.config.getoption("hw_port")
    username = request.config.getoption("hw_user")
    password = request.config.getoption("hw_password")

    logger.info(f"Connecting to hardware target at {host}:{port} as '{username}'")
    target = HwTarget(host, port, username, password)

    with target.ssh(timeout=10, n_retries=3, retry_interval=2) as ssh:
        result = ssh.execute_command("echo ok")
    if result != 0:
        raise RuntimeError(f"Hardware target at {host}:{port} is not reachable via SSH")
    logger.info(f"Hardware target at {host}:{port} is up")

    yield target
