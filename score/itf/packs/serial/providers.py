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
"""Serial console providers. Constructing a console opens nothing: `serial.open` (steps.py) does."""

from collections.abc import Iterator
from score.itf.core import capability

from .console import ConsoleConfig, SerialConsole
from .command import ConsoleLike, SerialExec
from .pty import PtyConsoleConfig, pty_opener


@capability("exec.console", label="console")
def make_console(config: ConsoleConfig) -> Iterator[SerialConsole]:
    console = SerialConsole(
        config["device"],
        baudrate=config.get("baudrate", 115200),
        logfile=config.get("logfile"),
        buffer=config.get("buffer", 20000),
        read_timeout=config.get("read_timeout", 0.2),
        stop_timeout=config.get("stop_timeout", 5.0),
    )
    try:
        yield console
    finally:
        console.close()


@capability("exec.console", label="pty_console")
def make_pty_console(config: PtyConsoleConfig) -> Iterator[SerialConsole]:
    """A console on a shell over a pseudo-terminal: a UART with something answering, for benches without
    hardware. Same object and members as `serial.console`."""
    console = SerialConsole(
        "pty:" + config.get("shell", "/bin/sh"),
        logfile=config.get("logfile"),
        buffer=config.get("buffer", 20000),
        read_timeout=config.get("read_timeout", 0.2),
        stop_timeout=config.get("stop_timeout", 5.0),
        opener=pty_opener(config.get("shell", "/bin/sh"), config.get("banner", "ITF PTY CONSOLE READY")),
    )
    try:
        yield console
    finally:
        console.close()


@capability("exec.command", label="exec")
def make_exec(console: ConsoleLike) -> SerialExec:
    return SerialExec(console)
