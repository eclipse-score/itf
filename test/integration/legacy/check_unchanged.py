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
"""The compatibility promise is tested, not edited: every test file in test/integration/legacy is byte-identical to its version
on main, so the layer cannot pass by changing the tests it keeps working."""

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent


def recorded() -> dict[str, str]:
    lines = (HERE / "main_tests.sha256").read_text(encoding="utf-8").splitlines()
    return {name: digest for digest, name in (line.split() for line in lines if line and not line.startswith("#"))}


def test_every_test_from_main_is_byte_identical():
    for name, digest in recorded().items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest, f"{name} differs from main"


def test_every_test_file_here_is_one_from_main():
    here = {p.name for p in HERE.glob("test_*.py")} | {"conftest.py"}
    assert here == set(recorded()), "test/integration/legacy holds only main's tests"
