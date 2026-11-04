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
"""itf_target: a valid target file becomes plan JSON at build time; an invalid one fails with ITF's diagnostics."""

import json
import os
import subprocess
from pathlib import Path


def _plan() -> dict:
    return json.loads(Path(os.environ["OK_PLAN"]).read_text(encoding="utf-8"))


def _run(tmp_path, target_file, *packs):
    out = tmp_path / "failing.plan.json"
    args = [os.environ["PLANNER"], "--target", os.environ[target_file], "--out", str(out)]
    for pack in packs:
        args += ["--pack", pack]
    return subprocess.run(args, capture_output=True, text=True), out


def test_plan_has_the_roles_and_the_steps():
    plan = _plan()
    assert set(plan) == {"target", "action", "assumptions"}
    assert plan["target"] and plan["action"]


def test_plan_names_the_roles_and_their_factories():
    roles = _plan()["target"]["nodes"]
    factories = {node["name"]: node["provider"] for node in roles}
    assert factories == {"command": "sim.exec", "platform": "sim.platform"}


def test_plan_orders_the_steps_that_bring_the_goal_up():
    steps = _plan()["action"]["steps"]
    assert [step["delivers"] for step in steps] == [["platform.up"]]
    assert steps[0]["impl"] == "score.itf.packs.sim.docker.steps:start_platform"
    assert steps[0]["uses"] == {"platform": "platform"}


def test_plan_file_is_deterministic():
    text = Path(os.environ["OK_PLAN"]).read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


def test_a_target_file_that_does_not_resolve_fails_with_rendered_diagnostics(tmp_path):
    run, out = _run(tmp_path, "NO_STORE", "sim")
    assert run.returncode == 1
    assert "plan failed at gate 1" in run.stderr
    assert "command (sim.exec) needs a 'platform.instance' for its slot 'platform'" in run.stderr
    assert "Candidates: sim.platform" in run.stderr
    assert not out.exists()


def test_a_factory_from_a_pack_that_is_not_in_packs_fails(tmp_path):
    run, out = _run(tmp_path, "OUTSIDE", "sim")
    assert run.returncode == 1
    assert "not in the itf_target's packs" in run.stderr and "localhost.platform" in run.stderr
    assert not out.exists()
    run, _ = _run(tmp_path, "OUTSIDE", "sim", "localhost")
    assert run.returncode == 0


def test_a_value_only_the_test_run_has_compiles_with_a_placeholder(tmp_path):
    run, out = _run(tmp_path, "UNSET", "sim")
    assert run.returncode == 0, run.stderr
    platform = next(n for n in json.loads(out.read_text())["target"]["nodes"] if n["name"] == "platform")
    assert platform["config"]["name"] == "${ITF_PLAN_TEST_NAME_SET_AT_TEST_TIME}"
