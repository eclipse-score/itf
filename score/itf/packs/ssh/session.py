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
"""`main`'s `Ssh` helper (`ssh.shell`): one instance is bound to one endpoint and holds at most one connection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Protocol
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # the SDK loads only when a part runs, never for a plan
    import paramiko

from . import client as ssh_client

logger = logging.getLogger(__name__)


class Endpoint(Protocol):
    __contract__ = "descriptor.endpoint"

    host: str
    port: int


class Credentials(Protocol):
    __contract__ = "descriptor.credentials"

    user: str
    password: str | None
    key_path: str | None


@dataclass(frozen=True)
class ShellConfig:
    timeout: int = 15
    keep_alive_interval: int | None = None
    n_retries: int = 5
    retry_interval: float = 1.0
    reuse_session: bool = True


class Ssh:
    endpoint: SimpleNamespace

    def __init__(
        self,
        target_ip: str,
        port: int = 22,
        timeout: int = 15,
        keep_alive_interval: int | None = None,
        n_retries: int = 5,
        retry_interval: int = 1,
        pkey_path: str | None = None,
        username: str = "root",
        password: str = "",
        reuse_session: bool = True,
        address=None,
    ):
        # `address`: an object with `host` and `port`, read again at every connect (a target file's endpoint role,
        # whose published port can change when the platform restarts); without it, target_ip and port are fixed.
        self._address = address
        self.endpoint = SimpleNamespace(host=target_ip, port=port)
        self._target_ip = target_ip
        self._port = port
        self._timeout = timeout
        self._keep_alive_interval = keep_alive_interval
        self._retries = n_retries
        self._retry_interval = retry_interval
        self._pkey_path = pkey_path
        self._username = username
        self._password = password
        self._reuse_session = reuse_session
        self._ssh: paramiko.SSHClient | None = None
        self._entered: list[Ssh | None] = []

    def _settings(self) -> dict:
        return {
            "target_ip": self._target_ip,
            "port": self._port,
            "timeout": self._timeout,
            "keep_alive_interval": self._keep_alive_interval,
            "n_retries": self._retries,
            "retry_interval": self._retry_interval,
            "pkey_path": self._pkey_path,
            "username": self._username,
            "password": self._password,
            "reuse_session": self._reuse_session,
            "address": self._address,
        }

    def connect(self) -> None:
        self.close()
        if self._address is not None:
            self._target_ip, self._port = self._address.host, self._address.port
            self.endpoint = SimpleNamespace(host=self._target_ip, port=self._port)
        logger.info("Connecting to %s:%s ...", self._target_ip, self._port)
        self._ssh = ssh_client.connect(
            self._target_ip,
            self._port,
            self._username,
            password=self._password,
            key_path=self._pkey_path,
            timeout=self._timeout,
            n_retries=self._retries,
            retry_interval=self._retry_interval,
            keep_alive_interval=self._keep_alive_interval,
        )

    def is_connected(self) -> bool:
        transport = self._ssh.get_transport() if self._ssh is not None else None
        return transport is not None and transport.is_active()

    def close(self) -> None:
        if self._ssh is not None:
            try:
                self._ssh.close()
            finally:
                self._ssh = None
                logger.info("Closed SSH connection.")

    def __enter__(self) -> Ssh:
        if not self.is_connected():
            self.connect()
            self._entered.append(self)
            return self
        if self._reuse_session:
            self._entered.append(None)
            return self
        fresh = Ssh(**self._settings())
        fresh.connect()
        self._entered.append(fresh)
        return fresh

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        opened = self._entered.pop()
        if opened is None:
            return
        if exc_type is not None:
            logger.debug(
                "SSH connection to %s failed unexpectedly: %s(%s)", self._target_ip, exc_type.__name__, exc_val
            )
        opened.close()

    def get_paramiko_client(self) -> paramiko.SSHClient | None:
        return self._ssh

    def execute_command_output(
        self,
        cmd: str,
        timeout: float = 30,
        max_exec_time: float = 180,
        logger_in: logging.Logger | None = None,
        verbose: bool = True,
        separate_stderr: bool = True,
    ) -> tuple[int, list[str], list[str]]:
        return ssh_client.execute_command_output(
            self._ssh,
            cmd,
            timeout=timeout,
            max_exec_time=max_exec_time,
            logger_in=logger_in,
            log=verbose,
            separate_stderr=separate_stderr,
        )

    def execute_command(
        self,
        cmd: str,
        timeout: float = 30,
        max_exec_time: float = 180,
        logger_in: logging.Logger | None = None,
        verbose: bool = True,
    ) -> int:
        logger.debug("Executing command: %s", cmd)
        logger.debug(
            "timeout: %s; max_exec_time: %s; logger_in: %s; verbose: %s;", timeout, max_exec_time, logger_in, verbose
        )
        exit_code, stdout_lines, stderr_lines = self.execute_command_output(
            cmd, timeout, max_exec_time, logger_in, verbose
        )
        if exit_code != 0:
            logger.debug("Exit code was %s.", exit_code)
            logger.debug("stdout_lines: %s", "\n".join(stdout_lines))
            logger.debug("stderr_lines: %s", "\n".join(stderr_lines))
        return exit_code
