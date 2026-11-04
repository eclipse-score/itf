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
"""Any target that runs commands (`command`): container API, SSH, serial, host."""

from typing import Protocol
from uuid import uuid4

import score.itf as itf


class Command(Protocol):
    __contract__ = "exec.command"

    def exec(self, command: str) -> tuple[int, bytes]: ...


itf_requires = itf.requires("command", shape=Command)


def test_output_and_exit_code_are_returned(target):
    assert target.command.exec("echo -n hello") == (0, b"hello")


def test_a_failing_command_reports_its_exit_code_without_raising(target):
    # A child shell: on a console the session itself persists, and a bare `exit` would end it.
    assert target.command.exec("sh -c 'exit 3'")[0] == 3


def test_stderr_is_part_of_the_output(target):
    code, output = target.command.exec("echo oops >&2")
    assert code == 0 and b"oops" in output


def test_commands_return_fresh_output_and_exit_status(target):
    token = "command_" + uuid4().hex
    status, output = target.command.exec(f"printf '{token}\\n'; sh -c 'exit 7'")
    assert status == 7
    assert token.encode("ascii") in output


def test_commands_preserve_output_without_a_trailing_newline(target):
    token = "command_" + uuid4().hex
    status, output = target.command.exec(f"printf '{token}'")
    assert status == 0
    assert token.encode("ascii") in output
