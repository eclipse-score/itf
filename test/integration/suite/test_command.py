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

import score.itf as itf


@itf.requires("command")
def test_output_and_exit_code_are_returned(target):
    assert target.command.exec("echo -n hello") == (0, b"hello")


@itf.requires("command")
def test_a_failing_command_reports_its_exit_code_without_raising(target):
    # A child shell: on a console the session itself persists, and a bare `exit` would end it.
    assert target.command.exec("sh -c 'exit 3'")[0] == 3


@itf.requires("command")
def test_stderr_is_part_of_the_output(target):
    code, output = target.command.exec("echo oops >&2")
    assert code == 0 and b"oops" in output
