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
"""Planning reads declarations only: loading a pack must not import the SDKs its parts use when they run.

Each pack's plugin is imported in a fresh interpreter, so modules other tests loaded do not hide an import.
"""

import subprocess
import sys

import pytest

# What a plan never calls: the Docker SDK (and requests under it), paramiko, pyserial.
HEAVY = ("docker", "paramiko", "requests", "urllib3", "serial")
PACKS = ("core_dump", "dlt", "docker", "localhost", "net", "pcap", "ping", "qemu", "serial", "ssh")


@pytest.mark.parametrize("pack", PACKS)
def test_loading_a_pack_for_a_plan_imports_no_sdk(pack):
    code = (
        "import sys\n"
        "from score.itf.core.engine import packs, registry\n"
        f"registry.expand([packs.load({pack!r})])  # what planning imports: the pack and the modules it lists\n"
        f"print(','.join(m for m in {HEAVY!r} if m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env={"PYTHONPATH": ":".join(sys.path)}
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"{pack} imports {result.stdout.strip()} at import time"
