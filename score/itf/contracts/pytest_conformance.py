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
"""pytest entrypoint for the contract conformance suites.

Load it as a plugin (`//score/itf/contracts:conformance` in `py_itf_test(plugins = ...)`) and give pytest one
test module that imports `test_conformance` (see `test/integration/conformance/test_conformance.py`). It
then runs one test per (node, check): every node of the session target whose contract has checks, against
every check of that contract. Optional checks (those needing members the node does not offer) are skipped
with the reason; checks that change the platform (restart) run last and the goals are reached again after
them. A selection of the run is possible with `-k`, e.g. `-k exec.command` or `-k docker.exec`.
"""

from __future__ import annotations

import pytest

from score.itf.core.engine.scopes import ROOT

from .conformance import Check, Skip, all_checks


def _cases(session) -> list:
    checks = all_checks(contracts={node.contract for node in session.target_plan.nodes})
    params = []
    for node in session.target_plan.nodes:
        offered = {member.name for member in node.gives.members}
        for item in checks.get(node.contract, ()):
            where = f"{node.scope}." if node.scope != ROOT else ""
            marks = []
            missing = [name for name in item.shape if name not in offered]
            if missing:
                marks.append(pytest.mark.skip(reason=f"{node.provider} does not offer {', '.join(missing)}"))
            ident = f"{where}{node.name}[{node.provider}]::{node.contract}::{item.name}"
            params.append(pytest.param(node.scope, node.name, item, id=ident, marks=marks))
    params.sort(key=lambda p: p.values[2].disruptive)  # stable: disruptive checks run last
    return params


def pytest_generate_tests(metafunc):
    if {"node_scope", "node_name", "conformance_check"} <= set(metafunc.fixturenames):
        session = getattr(metafunc.config, "_itf_session", None)
        params = _cases(session) if session is not None else []
        metafunc.parametrize(("node_scope", "node_name", "conformance_check"), params)


def test_conformance(target, node_scope, node_name, conformance_check: Check):
    """One check of one contract against one role of the target."""
    view = target if node_scope == ROOT else getattr(target, node_scope)
    node = view.get(node_name)
    try:
        conformance_check(node)
    except Skip as exc:
        pytest.skip(str(exc))
    finally:
        if conformance_check.disruptive:
            target.reach()  # bring every goal back so the checks after this one find a working target


__all__ = ["test_conformance"]
