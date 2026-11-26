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
"""Check that test/integration/legacy is ITF's integration suite from main, byte for byte, BUILD file included.

The compatibility layer must pass these tests as they were; it cannot pass by editing them. New tests for the
original API go to test/integration/compat, tests for the native API to the other integration suites.

Run from the repository root: `python3 tools/legacy_unchanged.py`. Exits 1 and names each difference."""

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGACY = ROOT / "test" / "integration" / "legacy"
RECORD = ROOT / "tools" / "gates" / "legacy_main.sha256"


def recorded() -> dict[str, str]:
    lines = RECORD.read_text(encoding="utf-8").splitlines()
    return {name: digest for digest, name in (line.split() for line in lines if line and not line.startswith("#"))}


def problems() -> list[str]:
    expected = recorded()
    found = []
    for name, digest in sorted(expected.items()):
        path = LEGACY / name
        if not path.is_file():
            found.append(f"{name}: missing")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            found.append(f"{name}: differs from main")
    extra = sorted({p.name for p in LEGACY.iterdir() if p.name != "__pycache__"} - expected.keys())
    found += [f"{name}: not one of main's files (new tests go to test/integration/compat)" for name in extra]
    return found


def main() -> int:
    found = problems()
    for problem in found:
        print(f"test/integration/legacy/{problem}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
