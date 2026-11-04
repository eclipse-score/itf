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
"""Starter tests for a serial console: run a command through it, read its recorded lines."""

import logging
from typing import Protocol

import score.itf as itf

log = logging.getLogger("starter.serial.test")


class Command(Protocol):
    __contract__ = "exec.command"

    def exec(self, command: str, /) -> tuple[int, bytes]: ...


class InteractiveConsole(Protocol):
    __contract__ = "exec.console"

    def mark(self) -> int: ...
    def write(self, text: str, /) -> None: ...
    def wait_for(self, pattern: str, /, *, timeout: float, since: int) -> str | None: ...
    def lines(self, *, since: int) -> list[str]: ...


@itf.requires("command", shape=Command)
def test_run_a_command(target):
    log.info("scenario: a command sent through the console returns exit 0 and its output")
    code, out = target.command.exec("echo hello-itf")
    log.info("verdict: exit %s, greeting present: %s", code, b"hello-itf" in out)
    assert code == 0
    assert b"hello-itf" in out


@itf.requires("console", shape=InteractiveConsole)
def test_read_recorded_lines(target):
    log.info("scenario: output sent to the console is recorded and can be read back line by line")
    mark = target.console.mark()
    target.console.write("echo recorded-marker\n")
    line = target.console.wait_for("recorded-marker", timeout=10, since=mark)
    lines = target.console.lines(since=mark)
    log.info("verdict: matched line %r among %d new line(s)", line, len(lines))
    assert line is not None, "the console must record what the target printed"
    assert any("recorded-marker" in entry for entry in lines)
