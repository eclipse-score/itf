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
"""Any target with a session shell (`shell`)."""

from typing import Protocol

import pytest

import score.itf as itf


class CommandExitCode(Protocol):
    __contract__ = "exec.shell"

    def execute_command(self, command: str, /) -> int: ...


class CommandOutput(Protocol):
    __contract__ = "exec.shell"

    def execute_command_output(self, command: str, /) -> tuple[int, list[str], list[str]]: ...


class SeparateCommandOutput(Protocol):
    __contract__ = "exec.shell"

    def execute_command_output(self, command: str, /, *, separate_stderr: bool) -> tuple[int, list[str], list[str]]: ...


class TimedCommandOutput(Protocol):
    __contract__ = "exec.shell"

    def execute_command_output(self, command: str, /, *, max_exec_time: float) -> tuple[int, list[str], list[str]]: ...


class Credentials(Protocol):
    __contract__ = "descriptor.credentials"

    user: str


itf_requires = [itf.requires("shell", contract="exec.shell")]


@itf.requires("shell", shape=CommandExitCode)
def test_execute_command_returns_the_exit_code(target):
    assert target.shell.execute_command("true") == 0
    assert target.shell.execute_command("exit 1") == 1


@itf.requires("shell", shape=SeparateCommandOutput)
def test_stdout_and_stderr_can_be_kept_apart_or_merged(target):
    code, out, err = target.shell.execute_command_output("echo out; echo err 1>&2; exit 7", separate_stderr=True)
    assert code == 7 and "out" in "".join(out) and "err" in "".join(err)
    code, out, err = target.shell.execute_command_output("echo out; echo err 1>&2; exit 7", separate_stderr=False)
    assert err == [] and "err" in "".join(out)


@itf.requires("shell", shape=CommandOutput)
def test_line_splitting_is_preserved(target):
    assert target.shell.execute_command_output("printf 'a\\nb\\n'") == (0, ["a\n", "b\n"], [])


@itf.requires("shell", shape=TimedCommandOutput)
def test_a_command_running_too_long_reports_minus_one(target):
    assert target.shell.execute_command_output("sleep 5", max_exec_time=1)[0] == -1


@itf.requires("shell", shape=CommandOutput)
@itf.requires("credentials", shape=Credentials)
def test_the_session_is_logged_in_as_the_target_files_user(target):
    code, out, _ = target.shell.execute_command_output("id -un")
    assert code == 0 and "".join(out).strip() == target.credentials.user


@itf.requires("shell", shape=TimedCommandOutput)
def test_large_output_is_captured_whole(target):
    line = "0123456789abcdef" * 16  # 256 characters, about 256 kB in all
    command = f"i=0; while [ $i -lt 1000 ]; do printf '{line}\\n'; i=$((i+1)); done"
    code, out, err = target.shell.execute_command_output(command, max_exec_time=180)
    assert code == 0 and err == [] and len("".join(out)) > 200_000
