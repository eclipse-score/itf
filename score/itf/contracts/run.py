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
"""Run each definition's conformance checks against the capability factories of given target files.

`run_conformance(target files, definitions, roots, overrides)` brings every target file up (it is the caller's choice
of target: a simulated one stands in for hardware), runs every check of the contract each role fulfils against
the role's object, and takes the target down again. A check that raises `Skip`, or whose required members the
role does not offer, is skipped with the reason; checks that disrupt the platform run last, and the goals are
reached again after them. `not_run(catalog, definitions, results)` lists the factories fulfilling a contract
with checks that no result covers: which ones could not be run, and why.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass

from .conformance import Skip, all_checks


@dataclass(frozen=True)
class Result:
    target_file: str
    role: str
    factory: str
    contract: str
    check: str
    status: str  # pass | fail | skip
    detail: str = ""


def run_conformance(target_files, definitions, roots=(), overrides=()) -> list[Result]:
    from score.itf.core import Session

    checks = all_checks(definitions)
    results: list[Result] = []
    for target_file in target_files:
        label = getattr(target_file, "describe", lambda: str(target_file))()
        with tempfile.TemporaryDirectory(prefix="itf-conformance-") as run_dir:
            session = Session(roots, target=target_file, overrides=overrides, run_dir=run_dir)
            try:
                session.resolve()
                session.bring_up()
                results += [_run_case(session, label, *case) for case in _cases(session, checks)]
            finally:
                session.close()
    return results


def _cases(session, checks) -> list:
    """(node, check, members the node offers) for every check of every role, disruptive checks last."""
    cases = []
    for node in session.target_plan.nodes:
        offered = {m.name for m in node.gives.members}
        cases += [(node, item, offered) for item in checks.get(node.contract, ())]
    return sorted(cases, key=lambda case: case[1].disruptive)  # stable


def _run_case(session, label: str, node, item, offered) -> Result:
    from score.itf.core.engine.scopes import ROOT

    where = f"{node.scope}." if node.scope != ROOT else ""
    base = dict(
        target_file=label, role=f"{where}{node.name}", factory=node.provider, contract=node.contract, check=item.name
    )
    missing = [m for m in item.shape if m not in offered]
    if missing:
        return Result(**base, status="skip", detail=f"does not offer {', '.join(missing)}")
    view = session.target if node.scope == ROOT else getattr(session.target, node.scope)
    try:
        item(view.get(node.name))
        return Result(**base, status="pass")
    except Skip as exc:
        return Result(**base, status="skip", detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - an AssertionError, or whatever the factory raised
        return Result(**base, status="fail", detail=f"{type(exc).__name__}: {exc}")
    finally:
        if item.disruptive:
            session.reach()


def not_run(catalog, definitions, results) -> list[str]:
    """`label (contract): reason` for each factory with checks to run that no target file exercised."""
    checks = all_checks(definitions)
    covered = {r.factory for r in results}
    return [
        f"{f.label} ({f.contract}): no target file given contains it"
        for f in sorted(catalog.factories.values(), key=lambda f: f.label)
        if f.contract in checks and f.label not in covered
    ]
