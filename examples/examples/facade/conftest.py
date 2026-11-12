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
"""Step 2 of the tutorial (README.md): the project's target API as a facade over the target file's roles.

The tests in this directory were written against `Ecu` (see before/ecu.py for what it used to be). They keep
calling `target.run`, `target.push` and `target.pull`; only what is under those methods changed.
"""

import pytest

import score.itf as itf


class Ecu(itf.Facade):
    """What the project's tests have always called a target, now written over the target file's roles."""

    # For tests that ask `target.has_capability("flash")`: a capability is the roles it needs.
    CAPABILITIES = {"exec": ("command",), "flash": ("command", "files")}

    def run(self, cmd: str) -> tuple[int, str]:
        code, output = self.role("command").exec(cmd)
        return code, output.decode()

    def push(self, local_path: str, remote_path: str) -> None:
        self.role("files").upload(local_path, remote_path)

    def pull(self, remote_path: str, local_path: str) -> None:
        self.role("files").download(remote_path, local_path)


# Step 3: the tests' `target` is the facade over ITF's target. Overriding a fixture with one that asks for the
# fixture it overrides is plain pytest; nothing else is needed.
@pytest.fixture(scope="session")
def target(target):
    return Ecu(target)
