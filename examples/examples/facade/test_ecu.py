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
"""The project's tests, as they were: written against its own target API (`Ecu`), unchanged by the move to ITF.
The last test is new-style, to show both kinds living in one suite while the project migrates at its own pace."""

import pytest


def test_runs_a_command(target):
    code, output = target.run("echo -n hello")
    assert (code, output) == (0, "hello")


def test_round_trips_a_file(target, tmp_path):
    if not target.has_capability("flash"):
        pytest.skip("this target cannot take files")
    (tmp_path / "image.bin").write_bytes(b"\x01\x02")
    target.push(str(tmp_path / "image.bin"), "/tmp/image.bin")
    target.pull("/tmp/image.bin", str(tmp_path / "back.bin"))
    assert (tmp_path / "back.bin").read_bytes() == b"\x01\x02"


def test_new_style_tests_share_the_target(target):
    assert target.command.exec("true")[0] == 0  # the facade passes every other name to the target
