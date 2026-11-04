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
"""One-shot commands through an SSH session node (`ssh.exec`)."""

from __future__ import annotations

import logging

from typing import Protocol
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # the SDK loads only when a part runs, never for a plan
    import paramiko

logger = logging.getLogger(__name__)


class Shell(Protocol):
    __contract__ = "exec.shell"

    def execute_command_output(
        self, cmd: str, timeout: float = 30, max_exec_time: float = 180
    ) -> tuple[int, list[str], list[str]]: ...
    def execute_command(self, cmd: str, timeout: float = 30) -> int: ...
    def get_paramiko_client(self) -> paramiko.SSHClient: ...


class SshExec:
    """`command` through the shell node: stdout and stderr merged, as bytes (what `docker.exec` returns too)."""

    def __init__(self, shell: Shell):
        self.shell = shell

    def exec(self, command: str, timeout: float = 30.0) -> tuple[int, bytes]:
        code, lines, _ = self.shell.execute_command_output(
            command, timeout=timeout, max_exec_time=180, separate_stderr=False
        )
        logger.info("ssh exec: %s -> exit %s", command, code)
        return code, "".join(lines).encode()


class SshCommandResult:
    def __init__(self, stdout, stderr, exit_code):
        self.__stdout = stdout
        self.__stderr = stderr
        self.__exit_code = exit_code

    def get_stdout_bytes(self):
        return self.__stdout

    def get_stderr_bytes(self):
        return self.__stderr

    def get_exit_code(self):
        return self.__exit_code


class SshCommand:
    """An SSH command started immediately and collected later through its original API."""

    def __init__(self, ssh_connection, cmd, ssh_connection_timeout=None):
        client = (
            ssh_connection.get_paramiko_client() if hasattr(ssh_connection, "get_paramiko_client") else ssh_connection
        )
        _, self.__stdout, self.__stderr = client.exec_command(cmd, timeout=ssh_connection_timeout)
        self.__stdout_bytes = None
        self.__stderr_bytes = None
        self.__exit_status = None

    def wait_until_finished(self, command_result_timeout) -> SshCommandResult:
        self.__stdout.channel.settimeout(command_result_timeout)
        self.__stdout_bytes = self.__stdout.read()
        self.__stderr_bytes = self.__stderr.read()
        self.__exit_status = self.__stdout.channel.recv_exit_status()
        return SshCommandResult(self.__stdout_bytes, self.__stderr_bytes, self.__exit_status)

    def is_finished(self) -> bool:
        return self.__stdout.channel.exit_status_ready()
