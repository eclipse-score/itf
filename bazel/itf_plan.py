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
"""The planner behind `itf_target`: compile a target file in plan-only mode, write the plan.

    itf_plan.py --target ecu.itf.yaml [--override lab.itf.yaml]... --pack docker... --out ecu.plan.json

Both gates run exactly as `--itf-plan` runs them (shapes are always strict) and nothing is constructed. A factory
label naming a pack that is not given with --pack fails. On a diagnostic the rendered report goes to stderr and
the exit status is 1.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from score.itf.core import (
    TargetFileError,
    ConfigValidationFailed,
    PackNotFound,
    ResolutionFailed,
    Session,
    TargetNameClash,
)
from score.itf.core.adapters.definitions import definitions
from score.itf.core.artifacts import plan_document
from score.itf.core.frontends import target_file as target_file_format

PLAN_KEYS = ("target", "action", "assumptions")


def check_packs(target_file: str, overrides: list[str], packs: list[str]) -> None:
    """Every factory label's pack must be one of `packs` (the `packs` of the `itf_target`)."""
    named = target_file_format.factory_labels(target_file_format.load_all(target_file, overrides))
    outside = sorted({label for label in named if label.split(".", 1)[0] not in (*packs, "local")})
    if outside:
        raise TargetFileError(
            "capability factories from packs that are not in the itf_target's packs "
            f"({', '.join(sorted(packs)) or 'none'}): {', '.join(outside)}; add the pack to packs = [...]"
        )


def plan(target_file: str, overrides: list[str], packs: list[str]) -> dict:
    """The plan of `target_file` with `overrides` merged over it: {"target", "action", "assumptions"}."""
    check_packs(target_file, overrides, packs)
    session = Session(
        target=target_file,
        overrides=overrides,
        plan_only=True,
        artifacts="none",
        unset="placeholder",  # a value only the test run has (a login) compiles as ${NAME}; nothing is built
        definitions=definitions(),
    ).resolve()
    document = json.loads(json.dumps(plan_document(session), default=str))
    return {key: document.get(key) for key in PLAN_KEYS}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", required=True, help="the target file (YAML)")
    parser.add_argument("--override", action="append", default=[], help="an override file, merged by role")
    parser.add_argument("--pack", action="append", default=[], help="a pack the target file may name")
    parser.add_argument("--contracts", action="append", default=[], help="a directory of contract definitions")
    parser.add_argument("--out", required=True, help="where to write <name>.plan.json")
    options = parser.parse_args(argv)
    target_file = os.path.abspath(options.target)
    overrides = [os.path.abspath(path) for path in options.override]
    out = os.path.abspath(options.out)
    if options.contracts:
        os.environ["ITF_CONTRACTS_PATH"] = os.pathsep.join(os.path.abspath(path) for path in options.contracts)
    try:
        result = plan(target_file, overrides, options.pack)
    except ResolutionFailed as exc:
        print(
            f"ITF: plan failed at gate {exc.gate} ({exc.phase}) for {options.target}\n{exc.rendered}",
            file=sys.stderr,
        )
        return 1
    except (TargetFileError, ConfigValidationFailed, TargetNameClash, PackNotFound, ValueError) as exc:
        print(f"ITF: target file {options.target} does not compile\n{exc}", file=sys.stderr)
        return 1
    Path(out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
