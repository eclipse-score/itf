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
"""Every target file the repository ships compiles: both gates and every setting, with placeholders for the values
only a test run has. It covers the target files no build compiles, such as the manual QEMU ones."""

import os
import subprocess
from pathlib import Path

import pytest

PACKS = ("core_dump", "dlt", "docker", "localhost", "net", "pcap", "ping", "qemu", "serial", "sim", "ssh")
ROOTS = (Path("test/integration/targets"), Path("score/itf/compat/targets"))


def target_files() -> list[Path]:
    return sorted(path for root in ROOTS for path in root.rglob("*.itf.yaml"))


def policy_of(target_file: Path) -> Path | None:
    """The policy ITF loads for it: beside it, else the nearest above it within its targets directory."""
    root = next(root for root in ROOTS if target_file.is_relative_to(root))
    for directory in (target_file.parent, *target_file.parent.parents):
        if (directory / "policy.py").is_file():
            return directory / "policy.py"
        if directory == root:
            return None
    return None


@pytest.mark.parametrize("target_file", target_files(), ids=str)
def test_the_target_file_compiles(target_file, tmp_path):
    args = [os.environ["PLANNER"], "--target", str(target_file), "--out", str(tmp_path / "plan.json")]
    args += [arg for pack in PACKS for arg in ("--pack", pack)]
    if (policy := policy_of(target_file)) is not None:
        args += ["--policy", str(policy)]
    done = subprocess.run(args, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_there_are_target_files_to_compile():
    assert len(target_files()) >= 10
