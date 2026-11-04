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
"""Any target with a recorded console (`console`): UART, an emulator's serial port."""

from typing import Protocol
from uuid import uuid4

import score.itf as itf


class RecordedConsole(Protocol):
    __contract__ = "exec.console"

    def lines(self) -> list[str]: ...


class InteractiveConsole(Protocol):
    __contract__ = "exec.console"

    def lines(self, since: int, /) -> list[str]: ...
    def mark(self) -> int: ...
    def write(self, text: str, /) -> None: ...
    def wait_for(self, pattern: str, /, *, timeout: float, since: int, regex: bool) -> str | None: ...


class CommandConsole(Protocol):
    __contract__ = "exec.console"

    def run(self, command: str, /, *, timeout: float) -> tuple[int, str]: ...


itf_requires = itf.requires("console", contract="exec.console")


@itf.requires("console", shape=RecordedConsole)
def test_the_console_recorded_output_since_it_opened(target):
    assert target.console.lines(), "the console recorded nothing since before boot"


@itf.requires("console", shape=InteractiveConsole)
def test_console_commands_produce_fresh_output(target):
    token = "console_" + uuid4().hex
    cursor = target.console.mark()
    target.console.write(f"printf '\\n{token}\\n'")
    assert target.console.wait_for(f"^{token}$", timeout=10, since=cursor, regex=True) == token
    assert token in target.console.lines(cursor)


@itf.requires("console", shape=CommandConsole)
def test_console_commands_return_output_and_exit_status(target):
    token = "console_" + uuid4().hex
    status, output = target.console.run(f"printf '{token}\\n'; sh -c 'exit 7'", timeout=10)
    assert status == 7
    assert token in output


@itf.requires("console", shape=CommandConsole)
def test_console_preserves_output_without_a_trailing_newline(target):
    token = "console_" + uuid4().hex
    status, output = target.console.run(f"printf '{token}'", timeout=10)
    assert status == 0
    assert token in output
