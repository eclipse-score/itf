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
"""The failure report a person reads when bring-up or a startup check fails."""

from types import SimpleNamespace as NS

from score.itf.core.engine.failure import bring_up_failure, checks_failure, teardown_failure

WIDTH = 60


def step(key, delivers=(), requires=(), uses=(), impl="mod:fn"):
    return NS(key=key, impl=impl, delivers=tuple(delivers or (key,)), requires=tuple(requires), uses=tuple(uses))


class Raised(Exception):
    pass


def failing(step, cause=None, **kw):
    err = Raised("the error")
    err.step, err.cause = step, cause
    err.states, err.executed, err.skipped = kw.get("states", ()), kw.get("executed", ()), kw.get("skipped", ())
    return err


PLAN = NS(steps=[step("a"), step("b", requires=["a"], uses=[("db", "store")]), step("c")])
TARGET = NS(nodes=[NS(ref="store", provider="p.store"), NS(ref="view", provider="p.view")])


def rows(failure):
    return dict(failure.rows)


def test_a_failing_action_says_what_failed_where_why_and_what_is_left():
    failure = bring_up_failure(
        failing(PLAN.steps[1], cause=ValueError("bad port"), executed=("a",)), PLAN, TARGET, "/run/1"
    )
    assert failure.title == "ITF: bring-up failed"
    assert [label for label, _ in failure.rows] == [
        "What failed",
        "Delivers",
        "Needed first",
        "Position",
        "Why",
        "Done before",
        "Not run",
        "Used roles",
        "Target",
        "Evidence",
    ]
    r = rows(failure)
    assert r["What failed"] == "action mod.fn" and r["Delivers"] == "b" and r["Needed first"] == "a"
    assert r["Position"] == "step 2 of 3" and r["Why"] == "ValueError: bad port"
    assert r["Done before"] == "ran a" and r["Not run"] == "c" and r["Used roles"] == "db=store"
    assert r["Target"] == "store (p.store), view (p.view)"
    assert r["Evidence"] == "/run/1  (log, plans and probe results of this run)"


def test_a_probe_that_says_no_after_a_clean_action_is_told_apart_from_an_exception():
    failure = bring_up_failure(failing(PLAN.steps[0], states=("x.up", "x.ready"), skipped=("z",)), PLAN, TARGET, "/r")
    r = rows(failure)
    assert r["Why"] == (
        "the action returned without error, but the check that proves it worked says x.up, x.ready does not hold"
    )
    assert r["Done before"] == "reused (already held) z" and r["Position"] == "step 1 of 3"
    assert "Needed first" not in r and "Used roles" not in r and r["Not run"] == "b, c"


def test_without_a_cause_the_error_text_is_the_reason_and_without_a_step_the_error_is_what_failed():
    failure = bring_up_failure(failing(None, executed=("a",), skipped=("b",)), PLAN, NS(nodes=[]), "/r")
    r = rows(failure)
    assert r["What failed"] == "the error" and r["Delivers"] == "-" and r["Why"] == "the error"
    assert "Position" not in r and r["Not run"] == "-" and r["Target"] == "-"
    assert r["Done before"] == "ran a; reused (already held) b"


def test_a_step_outside_the_plan_has_no_position_and_a_first_step_has_nothing_before_it():
    other = step("elsewhere", impl="")
    r = rows(bring_up_failure(failing(other, cause=Raised("x")), PLAN, TARGET, "/r"))
    assert "Position" not in r and r["What failed"] == "action ?" and r["Not run"] == "-"
    assert r["Done before"] == "nothing: this was the first step"


def test_a_cause_that_reads_like_a_timeout_adds_a_hint_and_renders_in_a_banner():
    failure = bring_up_failure(failing(PLAN.steps[0], cause=TimeoutError("timed out after 5s")), PLAN, TARGET, "/r")
    assert any("did not answer in time" in h for h in failure.hints)
    text = failure.render(WIDTH)
    lines = text.splitlines()
    assert lines[0].strip("=").strip() == "ITF: bring-up failed" and len(lines[0]) == WIDTH
    assert lines[1].startswith("What failed  action mod.fn") and lines[-1] == "=" * WIDTH
    assert "What to try" in lines


class Check(NS):
    pass


def test_startup_checks_list_failing_ones_first_then_the_rest_with_their_verdict():
    results = [
        Check(name="ok1", ok=True, detail="", essential=True),
        Check(name="hard", ok=False, detail="no route", essential=True),
        Check(name="soft", ok=False, detail="", essential=False),
        Check(name="bare", ok=False, detail="", essential=True),
    ]
    failure = checks_failure(results, "/run")
    assert failure.title == "ITF: startup checks failed"
    assert failure.rows == (
        ("FAILED", "hard: no route"),
        ("FAILED", "bare"),
        ("PASSED", "ok1"),
        ("WARNING", "soft"),
        ("Evidence", "/run"),
    )
    assert len(failure.hints) == 1 and "itf_verify hook" in failure.hints[0]


def test_teardown_problems_are_listed_and_a_clean_close_has_no_report():
    assert teardown_failure([("h", True, "")], NS(errors=()), "/r") is None
    failure = teardown_failure(
        [("h", False, "boom"), ("ok", True, "")], NS(errors=(("cam", "stuck"),)), "/r", leaked=["server"]
    )
    assert failure.rows == (
        ("hook", "h: boom"),
        ("role", "cam: stuck"),
        ("process", "server was still running at close and was terminated"),
        ("Evidence", "/r"),
    )
    assert len(failure.hints) == 2 and "ProcessWrapper" in failure.hints[1]


def test_without_a_run_directory_no_report_points_to_one():
    from score.itf.core.engine.failure import checks_failure

    check = NS(name="command.answers", ok=False, detail="exit 1", essential=True)
    assert "Evidence" not in checks_failure([check], None).render()
    assert "Evidence" in checks_failure([check], "/tmp/run").render()
