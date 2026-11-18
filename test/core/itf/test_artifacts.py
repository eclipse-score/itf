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
"""The run directory: what a session leaves behind after a good run, a failed gate and a failed bring-up, at each
artifact level: `none` (nothing), `standard` (what a person reads), `full` (every file ITF can write)."""

import json
from types import SimpleNamespace

import kv_parts
import pytest
import vault_parts

from score.itf.core import NotReady, ResolutionFailed, Session
from score.itf.core.artifacts import plan_document, write_artifacts

GOOD = "capabilities:\n  store: local.store\n  view: local.view\ngoals:\n  - state: kv.ready\n  - state: kv.seeded\n    by: local.seed_a\n"


@pytest.fixture(autouse=True)
def _clean_events():
    kv_parts.EVENTS.clear()


def session(tmp_path, target=GOOD, artifacts="full", **options):
    return Session(
        [kv_parts, vault_parts], target=target, run_dir=tmp_path / "run", reuse="fresh", artifacts=artifacts, **options
    )


SEEDED = "capabilities:\n  store: local.store\ngoals:\n  - state: kv.seeded\n    by: local.seed_a\n"


def files(tmp_path) -> set:
    run = tmp_path / "run"
    return {p.name for p in run.iterdir()} if run.exists() else set()


def test_standard_is_the_default_and_a_run_leaves_what_a_person_reads():
    assert Session().artifacts == "standard"


def test_standard_after_a_run_writes_the_plan_report_and_the_evidence(tmp_path):
    s = session(tmp_path, SEEDED, artifacts="standard").resolve()
    s.bring_up()
    s.close()
    assert files(tmp_path) == {"target.html", "evidence.html", "evidence.json"}


def test_standard_writes_nothing_for_a_plan_that_compiles(tmp_path):
    session(tmp_path, SEEDED, artifacts="standard", plan_only=True).resolve()
    assert files(tmp_path) == set()


def test_standard_explains_a_plan_that_fails(tmp_path):
    with pytest.raises(ResolutionFailed):
        session(tmp_path, "capabilities:\n  view: local.view\n", artifacts="standard").resolve()
    assert files(tmp_path) == {"diagnostics.txt"}
    assert "Gate 1" in (tmp_path / "run" / "diagnostics.txt").read_text()


def test_none_writes_nothing_after_a_run_or_a_failure(tmp_path):
    s = session(tmp_path, SEEDED, artifacts="none").resolve()
    s.bring_up()
    s.close()
    with pytest.raises(ResolutionFailed):
        session(tmp_path, "capabilities:\n  view: local.view\n", artifacts="none").resolve()
    assert not (tmp_path / "run").exists()


def test_an_unknown_artifact_level_is_refused():
    with pytest.raises(ValueError, match="artifacts"):
        Session(artifacts="debug")


def read_json(tmp_path, name):
    return json.loads((tmp_path / "run" / name).read_text())


def test_a_finished_run_leaves_every_artifact_describing_what_happened(tmp_path):
    s = session(tmp_path, "capabilities:\n  store: local.store\ngoals:\n  - state: kv.seeded\n    by: local.seed_a\n")
    s.resolve()
    s.bring_up()
    s.close()
    run = tmp_path / "run"
    assert {p.name for p in run.iterdir()} >= {
        "claims.json",
        "plan.json",
        "target.html",
        "diagnostics.txt",
        "gating.json",
        "run.json",
        "unwind.json",
    }
    plan = read_json(tmp_path, "plan.json")
    assert [n["contract"] for n in plan["target"]["nodes"]] == ["kv.store"]
    assert [step["key"] for step in plan["action"]["steps"]] == ["kv.seeded"]
    assert plan["action"]["steps"][0]["by"] == "local.seed_a"
    assert plan["assumptions"] == [] and plan["config_issues"] == []
    assert {f["name"] for f in plan["config_schemas"]["local.store"]} == {"name", "size"}
    assert read_json(tmp_path, "run.json")["executed"] == ["kv.seeded"]
    assert read_json(tmp_path, "unwind.json")["dismantled"] == ["store"]
    claims = read_json(tmp_path, "claims.json")
    assert {c["_kind"] for c in claims["setup"]} >= {"NodeClaim"}
    assert any(c["_kind"] == "GoalClaim" for c in claims["init"])
    assert (run / "diagnostics.txt").read_text() == ""
    assert "kv.seeded" in (run / "target.html").read_text()


def test_a_secret_is_redacted_in_the_claims_and_the_plan_but_the_session_still_has_it(tmp_path):
    target_file = (
        "capabilities:\n  vault:\n    factory: local.vault\n    with:\n      user: bob\n      password: hunter2\n"
    )
    s = session(tmp_path, target_file).resolve()
    run = tmp_path / "run"
    for name in ("claims.json", "plan.json", "target.html"):
        text = (run / name).read_text()
        assert "hunter2" not in text, name
        assert "bob" in text, name
    (node,) = [c for c in read_json(tmp_path, "claims.json")["setup"] if c.get("_kind") == "NodeClaim"]
    assert node["config"]["user"] == "bob" and node["config"]["password"] != "hunter2"
    assert s.target.vault.config["password"] == "hunter2"


def test_a_secret_copied_into_another_setting_is_masked_there_too(tmp_path, monkeypatch):
    monkeypatch.setenv("ITF_TEST_PASSWORD", "hunter2-is-long")
    target_file = (
        "capabilities:\n"
        "  vault:\n    factory: local.vault\n    with:\n      user: bob\n      password: ${ITF_TEST_PASSWORD}\n"
        "  store:\n    factory: local.store\n    with:\n      name: db?user=bob&password=${ITF_TEST_PASSWORD}\n"
    )
    s = session(tmp_path, target_file).resolve()
    run = tmp_path / "run"
    for name in ("claims.json", "plan.json", "target.html"):
        text = (run / name).read_text()
        assert "hunter2-is-long" not in text, name
        assert "password=[redacted]" in text, name
    assert "hunter2-is-long" not in json.dumps(plan_document(s))
    assert s.target.vault.config["password"] == "hunter2-is-long"


def test_a_failed_first_gate_leaves_the_diagnostics_and_no_plan_to_draw(tmp_path):
    with pytest.raises(ResolutionFailed):
        session(tmp_path, "capabilities:\n  view: local.view\n").resolve()
    run = tmp_path / "run"
    assert "Gate 1" in (run / "diagnostics.txt").read_text()
    assert read_json(tmp_path, "plan.json")["target"] is None
    assert read_json(tmp_path, "plan.json")["action"] is None
    assert not (run / "target.html").exists()


def test_a_failed_bring_up_still_writes_the_run_and_the_unwind(tmp_path):
    s = session(tmp_path, "capabilities:\n  store: local.store\ngoals:\n  - kv.broken\n").resolve()
    with pytest.raises(NotReady):
        s.bring_up()
    s.close()
    assert read_json(tmp_path, "run.json")["executed"] == []
    assert read_json(tmp_path, "unwind.json")["dismantled"] == ["store"]
    assert "kv.broken" in (tmp_path / "run" / "target.html").read_text()


def test_config_issues_are_listed_in_the_plan_and_the_diagnostics(tmp_path):
    s = session(tmp_path).resolve()
    s._config_issues = (("target.store", "local.store", "size must be positive"),)
    write_artifacts(tmp_path / "run", s)
    plan = read_json(tmp_path, "plan.json")
    assert plan["config_issues"] == [
        {"ref": "target.store", "provider": "local.store", "message": "size must be positive"}
    ]
    assert "size must be positive" in (tmp_path / "run" / "diagnostics.txt").read_text()


def test_gating_checks_teardown_and_unwind_are_written_as_the_session_recorded_them(tmp_path):
    s = session(tmp_path).resolve()
    s._gating_decisions = [
        ("t::a", SimpleNamespace(selected=True, reason="ok")),
        ("t::b", SimpleNamespace(selected=False, reason="no ssh")),
    ]
    s._check_results = [SimpleNamespace(name="ping", ok=False, detail="timeout", essential=True)]
    s._pre_observation = SimpleNamespace(holds=frozenset({"kv.ready", "kv.audited"}))
    s._probe_stats = {"bring_up": {"count": 2}}
    s._drift = ["kv.ready"]
    s._teardown_results = [("hook", False, "boom")]
    s._unwind_report = SimpleNamespace(kept=True, probed=("a",), dismantled=("b",), errors=(("c", "bad"),))
    write_artifacts(tmp_path / "run", s)
    assert read_json(tmp_path, "gating.json") == [
        {"test": "t::a", "selected": True, "reason": "ok"},
        {"test": "t::b", "selected": False, "reason": "no ssh"},
    ]
    run = read_json(tmp_path, "run.json")
    assert run["probed_before_gate2"] == ["kv.audited", "kv.ready"]
    assert run["checks"] == [{"name": "ping", "ok": False, "detail": "timeout", "essential": True}]
    assert run["probes"] == {"bring_up": {"count": 2}} and run["drift"] == ["kv.ready"]
    assert read_json(tmp_path, "unwind.json") == {
        "teardown_hooks": [{"name": "hook", "ok": False, "error": "boom"}],
        "kept": True,
        "probed": ["a"],
        "dismantled": ["b"],
        "errors": [{"ref": "c", "error": "bad"}],
    }


def test_with_a_cache_a_file_is_rewritten_only_when_its_inputs_changed(tmp_path):
    s = session(tmp_path).resolve()
    cache: dict = {}
    run = tmp_path / "run"
    write_artifacts(run, s, cache=cache)
    for name in ("plan.json", "target.html", "run.json", "claims.json"):
        (run / name).write_text("stale")
    write_artifacts(run, s, cache=cache)  # same objects: nothing is rewritten
    assert (run / "plan.json").read_text() == "stale" and (run / "target.html").read_text() == "stale"
    s._run_report = SimpleNamespace(executed=("kv.ready",), skipped=())
    write_artifacts(run, s, cache=cache)  # a new run report: the HTML and run.json follow, the plan does not
    assert (run / "plan.json").read_text() == "stale" and (run / "claims.json").read_text() == "stale"
    assert "<html" in (run / "target.html").read_text()
    assert read_json(tmp_path, "run.json")["executed"] == ["kv.ready"]
    write_artifacts(run, s)  # without a cache everything is written again
    assert (run / "plan.json").read_text() != "stale" and (run / "claims.json").read_text() != "stale"
