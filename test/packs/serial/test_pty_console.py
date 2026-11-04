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
"""A console on a shell over a pseudo-terminal: banner, commands, exit codes, restart."""

import pytest

from score.itf.packs.serial.command import SerialExec
from score.itf.packs.serial.console import SerialConsole
from score.itf.packs.serial.pty import pty_opener


@pytest.fixture
def console():
    console = SerialConsole("pty:/bin/sh", opener=pty_opener("/bin/sh", "READY-BANNER"), read_timeout=0.1)
    console.open()
    yield console
    console.close()


@pytest.fixture
def booted(console):
    """The console after its banner, as a bench waits for boot before sending commands."""
    assert console.wait_for("READY-BANNER", timeout=10, since=0)
    return console


def test_the_banner_printed_at_start_is_recorded(console):
    assert console.wait_for("READY-BANNER", timeout=10, since=0) == "READY-BANNER"


def test_run_returns_the_exit_code_and_the_output(booted):
    assert booted.run("echo hello", timeout=10) == (0, "hello")
    assert booted.run("exit_code_probe() { return 7; }; exit_code_probe", timeout=10)[0] == 7


def test_state_persists_between_commands_like_on_a_real_console(booted):
    booted.run("ITF_VALUE=42", timeout=10)
    assert booted.run("echo $ITF_VALUE", timeout=10) == (0, "42")


def test_exec_over_the_console_is_the_command_contract(booted):
    assert SerialExec(booted).exec("echo -n via-exec", timeout=10) == (0, b"via-exec")


def test_closing_stops_the_shell(console):
    pid = console._port._process.pid
    console.close()
    with pytest.raises(ProcessLookupError):
        import os

        os.kill(pid, 0)
