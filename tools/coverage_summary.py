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
"""Summarize a combined LCOV report as a Markdown table: line coverage in total and per area of score/itf.

    python3 tools/coverage_summary.py bazel-out/_coverage/_coverage_report.dat

An area is `score/itf/<part>` (`core`, `compat`, `cli`, `contracts`), and each pack on its own
(`score/itf/packs/<pack>`). Used by CI for the job summary; it only reads the report.
"""

import sys
from collections import defaultdict
from pathlib import Path


def area(path: str) -> str:
    parts = path.split("/")
    if parts[:3] == ["score", "itf", "packs"] and len(parts) > 4:
        return "/".join(parts[:4])
    return "/".join(parts[:3]) if parts[:2] == ["score", "itf"] and len(parts) > 3 else path


def read(report: Path) -> dict[str, list[int]]:
    """area -> [lines hit, lines found], counting each source file once (its best record wins)."""
    files: dict[str, tuple[int, int]] = {}
    current, hit, found = None, 0, 0
    for line in report.read_text(encoding="utf-8").splitlines():
        if line.startswith("SF:"):
            current, hit, found = line[3:], 0, 0
        elif line.startswith("LH:"):
            hit = int(line[3:])
        elif line.startswith("LF:"):
            found = int(line[3:])
        elif line == "end_of_record" and current:
            best = files.get(current, (0, 0))
            files[current] = max(best, (hit, found))
            current = None
    areas: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for path, (h, f) in files.items():
        areas[area(path)][0] += h
        areas[area(path)][1] += f
    return areas


def percent(hit: int, found: int) -> str:
    return f"{100 * hit / found:.1f}%" if found else "-"


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not Path(argv[1]).is_file():
        print("usage: coverage_summary.py <combined LCOV report>", file=sys.stderr)
        return 2
    areas = read(Path(argv[1]))
    total_hit = sum(h for h, _ in areas.values())
    total_found = sum(f for _, f in areas.values())
    print("## Coverage of score/itf\n")
    print(f"**{percent(total_hit, total_found)}** of {total_found} lines\n")
    print("| Area | Lines | Covered |")
    print("|---|---:|---:|")
    for name in sorted(areas):
        hit, found = areas[name]
        print(f"| `{name}` | {found} | {percent(hit, found)} |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
