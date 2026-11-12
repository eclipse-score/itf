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
"""An in-memory shell session over a simulated platform."""

from __future__ import annotations

from typing import Protocol


class Endpoint(Protocol):
    __contract__ = "descriptor.endpoint"

    host: str
    port: int


class Credentials(Protocol):
    __contract__ = "descriptor.credentials"

    user: str


class Platform(Protocol):
    __contract__ = "platform.instance"

    gen: int

    def exec(self, cmd: str) -> str: ...


class SimSession:
    """Dies when the simulated platform's generation changes, like a session across a reimage."""

    endpoint: Endpoint
    platform: Platform

    def __init__(self, endpoint: Endpoint, credentials: Credentials, platform: Platform):
        self.endpoint = endpoint
        self.credentials = credentials
        self.platform = platform
        self._gen: int | None = None

    def connect(self) -> None:
        self._gen = self.platform.gen

    def is_connected(self) -> bool:
        return self._gen is not None and self._gen == self.platform.gen

    def close(self) -> None:
        self._gen = None

    def execute_command_output(
        self,
        cmd: str,
        timeout: float = 30,
        max_exec_time: float = 180,
        logger_in=None,
        verbose: bool = True,
        separate_stderr: bool = True,
    ):
        if not self.is_connected():
            raise RuntimeError("shell session is dead (the platform changed under it)")
        output = self.platform.exec(cmd).encode("utf-8")
        return 0, output.decode("utf-8").splitlines(keepends=True), []

    def execute_command(
        self, cmd: str, timeout: float = 30, max_exec_time: float = 180, logger_in=None, verbose: bool = True
    ) -> int:
        return self.execute_command_output(cmd, timeout, max_exec_time, logger_in, verbose)[0]
