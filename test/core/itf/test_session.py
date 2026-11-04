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
"""One run: resolve, bring up, use, close."""

import json
from types import ModuleType

import fragile_parts
import kv_hooks
import kv_parts
import pytest
import recording_parts

from score.itf.core import NotReady, ResolutionFailed, Session, compose
from score.itf.core.engine import evidence

TARGET = """
capabilities:
  store: local.store
  view: local.view
goals:
  - state: kv.ready
  - state: kv.seeded
    by: local.seed_a
"""


@pytest.fixture(autouse=True)
def events():
    kv_parts.EVENTS.clear()
    return kv_parts.EVENTS


def run(tmp_path, target=TARGET, roots=(kv_parts,), **options):
    return Session(list(roots), target=target, run_dir=tmp_path / "run", **options)


def test_bring_up_runs_the_actions_in_dependency_order_and_close_unwinds(tmp_path, events):
    session = run(tmp_path, reuse="fresh").resolve()
    assert events == []  # resolving constructs nothing when nothing is probed
    session.bring_up()
    assert events == ["store built", "seed_a", "ready"]
    assert session.target.view.read("seeded") == "a"
    assert session.target.store.name == "mem"
    session.close()
    assert events[-1] == "store closed"


def test_the_target_is_a_handle_of_roles(tmp_path):
    session = run(tmp_path).resolve()
    assert session.target.names() == ("store", "view")
    assert session.target.has("view") and not session.target.has("shell")
    assert "kv.view" in session.target.tokens()
    with pytest.raises(AttributeError, match="no role or scope 'shell'"):
        session.target.shell


def test_hooks_of_the_project_run_after_bring_up_and_before_unwind(tmp_path, events):
    session = run(tmp_path, roots=(kv_parts, kv_hooks)).resolve()
    session.bring_up()
    assert session._check_results[0].ok
    store = session.target.store
    session.close()
    assert store.get("teardown") == "store, view"  # the teardown hook ran while the target still lived
    assert store.get("evidence_dir") == str(session.evidence_dir)
    assert events[-1] == "store closed"


def test_probes_make_a_second_run_reuse_what_holds(tmp_path, events):
    session = run(tmp_path).resolve()
    session.bring_up()
    done = len(events)
    session.reach("kv.ready")  # everything holds: nothing runs again
    assert events[done:] == []
    session.close()


def test_a_failing_action_is_not_ready_and_the_report_names_the_action(tmp_path):
    session = run(tmp_path, "capabilities:\n  store: local.store\ngoals:\n  - kv.broken\n").resolve()
    with pytest.raises(NotReady) as error:
        session.bring_up()
    assert "the store refused" in str(error.value.failure.render())
    session.close()


def test_a_plan_only_session_does_not_bring_up(tmp_path, events):
    session = run(tmp_path, plan_only=True).resolve()
    with pytest.raises(RuntimeError, match="plan_only"):
        session.bring_up()
    assert events == []


def test_resolution_failure_carries_the_gate_and_the_rendered_diagnostics(tmp_path):
    with pytest.raises(ResolutionFailed) as error:
        run(tmp_path, "capabilities:\n  view: local.view\n").resolve()
    assert error.value.gate == 1 and error.value.phase == "capabilities"
    assert "Gate 1" in error.value.rendered


@pytest.mark.parametrize("gating", ["skip", "fail"])
def test_policy_shapes_are_session_invariants_in_every_scope(tmp_path, events, gating):
    policy = ModuleType("infra_console_policy")
    exec(
        "from typing import Protocol\nclass Reader(Protocol):\n"
        "    __contract__ = 'kv.view'\n"
        "    def read(self, key: str, *, revision: int = 0) -> str: ...\n"
        "itf_expect = [Reader]\n",
        policy.__dict__,
    )
    target = (
        "capabilities:\n  store: local.store\n  view: local.view\n"
        "scopes:\n  device:\n    capabilities:\n      store: local.store\n      view: local.view\n"
    )
    with pytest.raises(ResolutionFailed) as error:
        run(tmp_path, target=target, roots=(kv_parts, policy), gating=gating).resolve()
    assert error.value.gate == 1
    assert {diagnostic.subject for diagnostic in error.value.diagnostics} == {"__itf_root__.view", "device.view"}
    assert all(diagnostic.code == "SHAPE_SIGNATURE_DRIFT" for diagnostic in error.value.diagnostics)
    assert events == []


def test_policy_expectations_compose_and_do_not_create_absent_roles(tmp_path, events):
    policies = []
    for name, contract, method in (
        ("read_policy", "kv.view", "def read(self, key: str) -> str: ..."),
        ("optional_console_policy", "exec.console", "def wait_for(self, pattern: str) -> str: ..."),
    ):
        policy = ModuleType(name)
        exec(
            f"from typing import Protocol\nclass API(Protocol):\n    __contract__ = {contract!r}\n    {method}\nitf_expect = API\n",
            policy.__dict__,
        )
        policies.append(policy)
    session = run(tmp_path, roots=(kv_parts, *policies)).resolve()
    assert len(session.catalog.expectations) == 2
    assert session.target.names() == ("store", "view")
    assert session.select({"test_without_console": ()})["test_without_console"].selected
    assert events == []


@pytest.mark.parametrize("major, matches", [(1, True), (2, False)])
def test_versioned_policy_expectations_apply_only_to_the_declared_major(tmp_path, major, matches):
    policy = ModuleType("version_policy")
    exec(
        "from typing import Protocol\nfrom score.itf import capability\n"
        "class Offering:\n    def read(self, key): ...\n"
        f"@capability('infra.reader@{major}', label='reader')\n"
        "def reader() -> Offering:\n    raise AssertionError('resolution must not construct')\n"
        "class Expected(Protocol):\n    __contract__ = 'infra.reader@1'\n"
        "    def read(self, key: str, *, revision: int = 0) -> str: ...\n"
        "itf_expect = Expected\n",
        policy.__dict__,
    )
    session = run(tmp_path, target="capabilities:\n  reader: local.reader\n", roots=(policy,))
    if matches:
        with pytest.raises(ResolutionFailed, match="policy expectations"):
            session.resolve()
    else:
        session.resolve()


def test_a_versioned_policy_refuses_an_unknown_provider_major(tmp_path):
    from score.itf.core import TargetFileError

    policy = ModuleType("unknown_version_policy")
    exec(
        "from typing import Protocol\nclass Reader(Protocol):\n"
        "    __contract__ = 'kv.view@1'\n    def read(self, key: str) -> str: ...\n"
        "itf_expect = Reader\n",
        policy.__dict__,
    )
    with pytest.raises(TargetFileError, match="policy contract major unknown"):
        run(tmp_path, roots=(kv_parts, policy)).resolve()


def test_policy_reports_unknown_versions_and_shape_differences_together(tmp_path):
    from score.itf.core import TargetFileError

    policy = ModuleType("mixed_policy")
    exec(
        "from typing import Protocol\nclass Reader(Protocol):\n"
        "    __contract__ = 'kv.view@1'\n    def read(self, key: str) -> str: ...\n"
        "class Store(Protocol):\n    __contract__ = 'kv.store'\n"
        "    def missing_policy_method(self) -> None: ...\n"
        "itf_expect = [Reader, Store]\n",
        policy.__dict__,
    )
    with pytest.raises(TargetFileError) as error:
        run(tmp_path, roots=(kv_parts, policy)).resolve()
    assert "policy contract major unknown" in str(error.value)
    assert "missing_policy_method" in str(error.value)


def test_policy_expectations_for_one_contract_do_not_override_or_leak(tmp_path, events):
    policies = []
    for name, signature in (
        ("first_policy", "self, key: str, *, unsupported: bool = False"),
        ("second_policy", "self, key: str"),
    ):
        policy = ModuleType(name)
        exec(
            "from typing import Protocol\nclass Reader(Protocol):\n"
            f"    __contract__ = 'kv.view'\n    def read({signature}) -> str: ...\n"
            "itf_expect = Reader\n",
            policy.__dict__,
        )
        policies.append(policy)
    with pytest.raises(ResolutionFailed) as error:
        run(tmp_path, roots=(kv_parts, *policies)).resolve()
    assert any(("policy", "first_policy") in diagnostic.evidence for diagnostic in error.value.diagnostics)
    assert run(tmp_path).resolve().catalog.expectations == ()
    assert events == []


def test_plans_print_roles_factory_labels_and_contract_names(tmp_path):
    session = run(tmp_path, plan_only=True).resolve()
    plan = session.target.plan()
    labels = [n["label"] for n in plan["target"]["nodes"]]
    assert labels == ["store (local.store)", "view (local.view)"]
    assert plan["target"]["nodes"][0]["contract"] == "kv.store"
    assert [s["delivers"] for s in plan["action"]["steps"]] == [["kv.seeded"], ["kv.ready"]]
    assert [s["by"] for s in plan["action"]["steps"]] == ["local.seed_a", "local.ready"]


@pytest.mark.parametrize("major", [1, 2])
def test_versioned_state_goals_select_only_the_matching_action(tmp_path, major, monkeypatch):
    import sys

    policy = ModuleType("versioned_states")
    monkeypatch.setitem(sys.modules, policy.__name__, policy)
    exec(
        "from score.itf import state\nEVENTS = []\n"
        "@state('service.ready@1', label='ready_v1')\n"
        "def ready_v1(): EVENTS.append(1)\n"
        "@ready_v1.probe\ndef is_ready_v1(): return 1 in EVENTS\n"
        "@state('service.ready@2', label='ready_v2')\n"
        "def ready_v2(): EVENTS.append(2)\n"
        "@ready_v2.probe\ndef is_ready_v2(): return 2 in EVENTS\n",
        policy.__dict__,
    )
    session = run(tmp_path, roots=(policy,), target=f"goals:\n  - service.ready@{major}\n").resolve()
    assert policy.EVENTS == []
    try:
        session.bring_up()
        assert policy.EVENTS == [major]
        assert f"service.ready@{major}" in session.target.states()
        assert f"service.ready@{3 - major}" not in session.target.states()
    finally:
        session.close()


def test_compose_is_a_context_manager(tmp_path, events):
    with compose([kv_parts], target=TARGET, run_dir=tmp_path / "run") as session:
        assert session.target.store.get("seeded") == "a"
    assert events[-1] == "store closed"


def test_score_itf_session_is_the_core_session_and_definitions_are_handed_in_when_wanted(tmp_path):
    import score.itf as itf

    assert itf.Session is Session
    without = itf.Session([kv_parts], target=TARGET, plan_only=True, run_dir=tmp_path / "run").resolve()
    assert without.definitions == {} and without.warnings == ()
    from score.itf.core.adapters.definitions import definitions

    handed = itf.Session(
        [kv_parts], target=TARGET, plan_only=True, run_dir=tmp_path / "run2", definitions=definitions()
    ).resolve()
    assert handed.definitions == definitions()


def test_the_session_is_read_through_public_accessors(tmp_path):
    session = run(tmp_path).resolve()
    assert session.target_plan.nodes and session.catalog.factories
    assert session.action_plan.steps and session.observed == frozenset()
    session.bring_up()
    assert session.observed
    session.close()


@pytest.mark.parametrize("option, value", [("gating", "strict"), ("reuse", "always"), ("on_exit", "stay")])
def test_the_modes_are_validated(option, value):
    with pytest.raises(ValueError, match=f"{option} is one of"):
        Session(**{option: value})


def test_a_deprecated_contract_in_the_definitions_warns(tmp_path):
    from score.itf.core.gating import Definition

    definitions = {"kv.store": Definition("kv.store", 1, "deprecated", "kv.map")}
    session = run(tmp_path, plan_only=True, definitions=definitions).resolve()
    assert any("kv.store" in w and "deprecated" in w and "kv.map" in w for w in session.warnings)


REC = "capabilities:\n  thing: local.thing\ngoals:\n  - rec.ready\n"


@pytest.fixture
def calls():
    recording_parts.CALLS.clear()
    recording_parts.HOLDS[:] = [False]
    return recording_parts.CALLS


def test_resolve_is_a_pure_plan_it_probes_and_builds_nothing(tmp_path, calls):
    recording_parts.HOLDS[:] = [True]
    session = run(tmp_path, target=REC, roots=(recording_parts,)).resolve()
    assert calls == []
    assert [s.impl.rpartition(":")[2] for s in session.action_plan.steps] == ["make_ready"]
    session.select({"some_test": ()})
    assert calls == []


def test_bring_up_probes_first_and_runs_only_what_does_not_hold(tmp_path, calls):
    recording_parts.HOLDS[:] = [True]
    session = run(tmp_path, target=REC, roots=(recording_parts,)).resolve()
    session.bring_up()
    assert "run" not in calls and "probe" in calls
    assert session.action_plan.steps == ()  # the delta: what holds is not planned again
    session.close()


def test_bring_up_runs_an_action_whose_probe_says_no(tmp_path, calls):
    session = run(tmp_path, target=REC, roots=(recording_parts,)).resolve()
    session.bring_up()
    assert calls.index("probe") < calls.index("run")
    session.close()


def test_renew_delivers_again_what_an_earlier_reach_delivered(tmp_path, events):
    session = run(tmp_path, target="capabilities:\n  store: local.store\n").resolve()
    session.bring_up()
    session.reach("kv.audited")
    assert events.count("audit") == 1
    session.renew("store")
    assert events.count("audit") == 2  # the goal reached earlier is a goal of the delta too
    assert events.count("store built") == 2
    session.close()


def test_discard_dismantles_a_role_and_the_next_reach_builds_it_afresh(tmp_path, events):
    session = run(tmp_path, target="capabilities:\n  store: local.store\n").resolve()
    session.bring_up()
    session.reach("kv.audited")
    old = session.target.store
    session.discard("store")
    assert events.count("store built") == 1 and events.count("audit") == 1  # nothing rebuilt or reached yet
    fresh = session.target.store  # a new object the caller may adjust before reaching
    assert fresh is not old
    session.reach("kv.audited")
    assert events.count("audit") == 2  # the old evidence was forgotten, so the action runs again
    session.close()


FRAGILE = "capabilities:\n  machine: local.machine\ngoals:\n  - box.linked\n"


@pytest.fixture
def fragile():
    fragile_parts.PANIC_BOOTS.clear()
    fragile_parts.BROKEN_LINK[0] = False
    return fragile_parts


def test_bring_up_plans_again_when_a_state_it_had_stops_holding(tmp_path, fragile):
    fragile.PANIC_BOOTS.add(1)  # the first boot dies; the second holds
    session = run(tmp_path, FRAGILE, roots=(fragile,), bring_up_attempts=3).resolve()
    session.bring_up()
    assert session.target.machine.boots == 2 and session.target.machine.linked
    session.close()


def test_bring_up_gives_up_after_its_attempts(tmp_path, fragile):
    fragile.PANIC_BOOTS.update({1, 2, 3})
    session = run(tmp_path, FRAGILE, roots=(fragile,), bring_up_attempts=2).resolve()
    with pytest.raises(NotReady, match="no banner"):
        session.bring_up()
    assert session.target.machine.boots == 2
    session.close()


def test_a_failure_that_loses_no_state_is_not_retried(tmp_path, fragile):
    fragile.BROKEN_LINK[0] = True  # the machine stays up: planning again would change nothing
    session = run(tmp_path, FRAGILE, roots=(fragile,), bring_up_attempts=3).resolve()
    with pytest.raises(NotReady, match="the link refused"):
        session.bring_up()
    assert session.target.machine.boots == 1
    session.close()


def test_one_attempt_is_the_default(tmp_path, fragile):
    fragile.PANIC_BOOTS.add(1)
    session = run(tmp_path, FRAGILE, roots=(fragile,)).resolve()
    with pytest.raises(NotReady):
        session.bring_up()
    assert session.target.machine.boots == 1
    session.close()


def test_the_evidence_tells_a_retried_attempt_from_a_failure(tmp_path, fragile):
    fragile.PANIC_BOOTS.add(1)
    session = run(tmp_path, FRAGILE, roots=(fragile,), bring_up_attempts=2, artifacts="full").resolve()
    session.bring_up()
    record = evidence.build_record(session)
    session.close()

    assert record["outcome"] == "ok"  # the run recovered: the failed attempt does not fail it
    steps = [(s["step"].split(":")[-1], s["attempt"], s["outcome"]) for s in record["steps"]]
    assert steps == [
        ("box.up", 1, "ok"),
        ("box.linked", 1, "failed, retried"),
        ("box.up", 2, "ok"),
        ("box.linked", 2, "ok"),
    ]
    assert [(r["attempt"], r["lost"]) for r in record["retries"]] == [(1, ["box.up"])]
    assert "no banner" in record["retries"][0]["error"]
    assert any(p["phase"] == "bring_up_lost_check" for p in record["probes"])  # the probes that decided it
    page = evidence.render_html(record)
    assert "attempt 1 failed" in page and "box.up stopped holding" in page
    assert evidence.summarize([session.run_dir])["failing_steps"] == []
    assert "attempt 1 retried: box.up stopped holding" in (session.run_dir / "target.html").read_text()
    assert json.loads((session.run_dir / "run.json").read_text())["retries"][0]["lost"] == ["box.up"]


def test_a_target_with_no_action_steps_says_there_is_nothing_to_bring_up(tmp_path, caplog):
    caplog.set_level("INFO", logger="score.itf.core")
    session = run(tmp_path, FRAGILE.split("goals:")[0], roots=(fragile_parts,)).resolve()
    session.bring_up()
    session.close()
    assert "nothing to bring up: the resolved action plan has no steps" in caplog.text


def test_an_assumed_goal_logs_its_owner_and_reason_without_claiming_no_goals(tmp_path, caplog):
    caplog.set_level("INFO", logger="score.itf.core")
    session = Session(
        target="goals:\n  - external.ready\nassume:\n  - state: external.ready\n    owner: lab\n"
        "    reason: managed by the rack\n",
        run_dir=tmp_path / "run",
    )
    session.secrets.add("managed by the rack")
    session.resolve()
    assert not session.action_plan.steps
    session.bring_up()
    session.close()
    assert "assumed external.ready (owner: lab; reason: [redacted])" in caplog.text
    assert "nothing to bring up: the resolved action plan has no steps" in caplog.text
    assert "has no goals" not in caplog.text
    event = next(
        record.itf_event for record in caplog.records if record.getMessage().startswith("assumed external.ready")
    )
    assert event["reason"] == "[redacted]"
