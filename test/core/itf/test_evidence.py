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
"""The run evidence: the record a closed session leaves, the page projected from it, and the summary over runs."""

import json
from types import SimpleNamespace as NS

import pytest

from score.itf.core.engine import evidence


def planned(*keys):
    return NS(steps=[NS(key=k, impl=f"m:{k}", delivers=(k,), requires=()) for k in keys])


def finished(step, t, ok=True, phase="bring_up", error=""):
    return {"kind": "action_finished", "step": step, "t": t, "ok": ok, "phase": phase, "error": error}


def session(tmp_path, **attrs):
    base = dict(
        run_dir=tmp_path / "run-7",
        _target_plan=NS(nodes=[NS(ref="store", provider="p.store", contract="kv.store")], scopes=lambda: ["b", "a"]),
        _action_plan=planned("s1", "s2", "s3", "s4"),
        _full_plan=planned("s1", "s2", "s3", "s4", "s5"),
        _events=[
            {"kind": "action_started", "step": "s1", "t": 1.0},
            finished("s1", 1.25),
            {"kind": "action_started", "step": "s2", "t": 2.0},
            finished("s2", 2.5, ok=False, error="RuntimeError('no')"),
            {"kind": "action_skipped", "step": "s3", "phase": "bring_up", "reason": "already held"},
            {"kind": "state_probed", "phase": "bring_up", "step": "s1", "states": ["a"], "ok": True, "ms": 1.23456},
            {"kind": "state_probed", "phase": "unwind", "ok": None, "error": "boom"},
            {"kind": "other"},
        ],
        _check_results=[],
        _teardown_results=[],
        _unwind_report=None,
        _probe_stats={"bring_up": {"count": 1}},
        _drift=["x"],
        _leaked_processes=["proc"],
        _ready=True,
    )
    return NS(**{**base, **attrs})


def test_the_record_lists_what_ran_failed_was_skipped_or_never_started_in_that_order(tmp_path):
    record = evidence.build_record(session(tmp_path))
    assert record["schema"] == 1 and record["run"] == "run-7" and record["ready"] is True
    assert [(s["step"], s["outcome"], s["phase"], s["ms"], s["error"]) for s in record["steps"]] == [
        ("s1", "ok", "bring_up", 250.0, ""),
        ("s2", "failed", "bring_up", 500.0, "RuntimeError('no')"),
        ("s3", "skipped", "bring_up", 0.0, "already held"),
        ("s4", "not run", "", 0.0, ""),
    ]
    assert record["outcome"] == "failed"  # a step failed


def test_the_record_summarises_the_plan_the_probes_and_what_was_left_behind(tmp_path):
    record = evidence.build_record(session(tmp_path))
    assert record["plan"] == {
        "nodes": [{"ref": "store", "provider": "p.store", "contract": "kv.store"}],
        "scopes": ["a", "b"],
        "planned_steps": [
            {"key": k, "impl": f"m:{k}", "delivers": [k], "requires": []} for k in ("s1", "s2", "s3", "s4")
        ],
        "full_plan_steps": 5,
    }
    assert record["probes"] == [
        {"phase": "bring_up", "step": "s1", "states": ["a"], "ok": True, "ms": 1.235, "error": ""},
        {"phase": "unwind", "step": "", "states": [], "ok": None, "ms": 0.0, "error": "boom"},
    ]
    assert record["probe_totals"] == {"bring_up": {"count": 1}} and record["drift"] == ["x"]
    assert record["leaked_processes"] == ["proc"] and record["unwind"] == {"kept": None, "dismantled": [], "errors": []}


def test_a_run_with_nothing_wrong_is_ok_and_one_with_a_failed_essential_check_or_a_failure_text_is_not(tmp_path):
    clean = dict(_events=[finished("s1", 1.0)], _action_plan=planned("s1"))
    assert evidence.build_record(session(tmp_path, **clean))["outcome"] == "ok"
    soft = NS(name="n", ok=False, detail="d", essential=False)
    hard = NS(name="h", ok=False, detail="why", essential=True)
    assert evidence.build_record(session(tmp_path, **clean, _check_results=[soft]))["outcome"] == "ok"
    bad = evidence.build_record(session(tmp_path, **clean, _check_results=[hard]))
    assert bad["outcome"] == "failed" and bad["checks"] == [
        {"name": "h", "ok": False, "detail": "why", "essential": True}
    ]
    assert evidence.build_record(session(tmp_path, **clean, _failure_text="boom"))["failure"] == "boom"
    rendered = NS(rendered="Gate 1 text")
    from_gate = evidence.build_record(session(tmp_path, **clean, _resolution_failure=rendered))
    assert (from_gate["outcome"], from_gate["failure"]) == ("failed", "Gate 1 text")


def test_teardown_results_and_the_unwind_report_are_recorded(tmp_path):
    unwind = NS(kept=True, dismantled=("a", "b"), errors=(("c", "bad"),))
    record = evidence.build_record(
        session(tmp_path, _teardown_results=[("hook", False, "boom")], _unwind_report=unwind)
    )
    assert record["teardown"] == [{"name": "hook", "ok": False, "error": "boom"}]
    assert record["unwind"] == {"kept": True, "dismantled": ["a", "b"], "errors": [{"ref": "c", "error": "bad"}]}


def test_a_session_that_never_planned_has_an_empty_record(tmp_path):
    record = evidence.build_record(NS(run_dir=tmp_path / "r"))
    assert record["plan"] == {"nodes": [], "scopes": [], "planned_steps": [], "full_plan_steps": 0}
    assert record["steps"] == [] and record["outcome"] == "ok" and record["ready"] is False


def test_write_evidence_leaves_the_json_and_a_page_that_can_be_regenerated_from_it(tmp_path):
    page_path = evidence.write_evidence(tmp_path / "out", session(tmp_path))
    assert page_path == tmp_path / "out" / "evidence.html"
    record = json.loads((tmp_path / "out" / "evidence.json").read_text())
    assert record["run"] == "run-7"
    first = page_path.read_text()
    page_path.unlink()
    assert evidence.write_html(tmp_path / "out") == page_path and page_path.read_text() == first
    with pytest.raises(FileNotFoundError, match="no evidence record"):
        evidence.load_record(tmp_path / "nowhere")


def test_the_page_shows_the_outcome_the_steps_the_probes_and_the_leaks(tmp_path):
    page = evidence.render_html(evidence.build_record(session(tmp_path)))
    assert "<title>itf evidence run-7</title>" in page
    assert '<span class="badge bad">failed</span>' in page and "ready: yes" in page
    assert "<h2>Failure</h2>" not in page
    assert '<td><code>s1</code></td><td><span class="ok">ok</span></td><td>bring_up</td>' in page
    assert '<span class="bad">failed</span>' in page and '<span class="muted">skipped</span>' in page
    assert '<span class="muted">not run</span>' in page
    assert "500.0 ms" in page and 'class="bar" style="width:200px"' in page  # the longest step is the full bar
    assert "250.0 ms" in page and 'style="width:100px"' in page
    assert '<span class="ok">held</span>' in page and '<span class="bad">error</span>' in page
    assert '<p class="bad">proc</p>' in page and "none: no process outlived the run" not in page


def test_the_page_of_a_clean_run_says_nothing_leaked_and_lists_checks_hooks_and_unwind_errors(tmp_path):
    hard = NS(name="ping", ok=True, detail="fast", essential=True)
    soft = NS(name="disk", ok=False, detail="full", essential=False)
    unwind = NS(kept=True, dismantled=("store",), errors=(("cam", "stuck"),))
    s = session(
        tmp_path,
        _events=[],
        _action_plan=planned(),
        _leaked_processes=[],
        _check_results=[hard, soft],
        _teardown_results=[("hook", True, ""), ("hook2", False, "boom")],
        _unwind_report=unwind,
    )
    record = evidence.build_record(s)
    page = evidence.render_html(record)
    assert '<span class="badge ok">ok</span>' in page and "none: no process outlived the run" in page
    assert '<td>ping</td><td><span class="ok">ok</span></td><td>yes</td><td>fast</td>' in page
    assert '<td>disk</td><td><span class="bad">failed</span></td><td>no</td><td>full</td>' in page
    assert '<td>hook2</td><td><span class="bad">failed</span></td><td>boom</td>' in page
    assert "dismantled: store (kept: not unwound)</p>" in page and '<p class="bad">cam: stuck</p>' in page
    assert '<p class="muted">none</p>' in page  # the empty steps table
    failing = evidence.render_html({**record, "failure": "<it broke>", "unwind": {}})
    assert "<h2>Failure</h2><pre>&lt;it broke&gt;</pre>" in failing and "dismantled: -</p>" in failing


def test_the_page_of_an_empty_record_still_renders():
    page = evidence.render_html({})
    assert '<span class="badge bad">failed</span>' in page and "ready: no" in page


def write_run(tmp_path, name, **record):
    run = tmp_path / name
    run.mkdir()
    (run / "evidence.json").write_text(json.dumps({"outcome": "ok", **record}), encoding="utf-8")
    return run


def probe(step, ms, ok=True):
    return {"step": step, "ms": ms, "ok": ok}


def test_the_summary_ranks_probes_by_time_and_lists_the_false_and_failing_ones_across_runs(tmp_path):
    one = write_run(tmp_path, "a", probes=[probe("slow", 30.0), probe("flaky", 1.0, False)], steps=[])
    two = write_run(
        tmp_path,
        "b",
        outcome="failed",
        probes=[probe("slow", 10.0), probe("flaky", 2.0), probe("err", 0.5, None)],
        steps=[{"step": "boom", "outcome": "failed", "error": "e1"}, {"step": "fine", "outcome": "ok", "error": ""}],
    )
    summary = evidence.summarize([one, two], top=2)
    assert (summary["runs"], summary["failed_runs"]) == (2, 1)
    assert summary["slowest_probes"] == [
        {"step": "slow", "max_ms": 30.0, "total_ms": 40.0, "count": 2, "mean_ms": 20.0},
        {"step": "flaky", "max_ms": 2.0, "total_ms": 3.0, "count": 2, "mean_ms": 1.5},
    ]
    assert summary["probes_false_at_least_once"] == [
        {"step": "flaky", "false": 1, "count": 2},
        {"step": "err", "false": 1, "count": 1},
    ]
    assert summary["failing_steps"] == [{"step": "boom", "failures": 1, "last_error": "e1"}]


def test_the_summary_text_has_one_section_per_list_and_a_dash_for_an_empty_one(tmp_path):
    summary = evidence.summarize([write_run(tmp_path, "a", probes=[probe("slow", 3.0, False)], steps=[])])
    assert evidence.render_summary(summary).splitlines() == [
        "1 run(s), 0 failed",
        "",
        "Slowest probes (max ms)",
        "        3.0  mean      3.0  x1   slow",
        "",
        "Probes that were false at least once",
        "  1/1  slow",
        "",
        "Failing steps",
        "  -",
    ]
    empty = evidence.render_summary(evidence.summarize([]))
    assert empty.splitlines()[0] == "0 run(s), 0 failed" and empty.count("  -") == 3
