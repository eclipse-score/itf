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
"""`@itf.requires`: a test is deselected, with a reason, when the role is missing, is another contract or lacks members."""

import kv_parts
import pytest
from types import SimpleNamespace
from typing import Protocol
from dataclasses import replace

import score.itf as itf
from score.itf.core import Session
from score.itf.core.gating import Requirement, get_requirements

TARGET_FILE = """
capabilities:
  store: local.store
  reader: local.view
  slim: local.slim_view
"""


@pytest.fixture
def session(tmp_path):
    return Session([kv_parts], target=TARGET_FILE, plan_only=True, run_dir=tmp_path / "run").resolve()


def decide(session, *requirements):
    return session.select({"t": tuple(requirements)})["t"]


def test_requires_collects_requirements_on_the_test():
    @itf.requires("store")
    @itf.requires("reader", contract="kv.view@1", shape=["read"])
    def test_something(): ...

    assert get_requirements(test_something) == (
        Requirement("reader", "kv.view", ("read",), None, 1),
        Requirement("store"),
    )


def test_requires_takes_a_role_name():
    with pytest.raises(TypeError, match="role name"):
        itf.requires(None)
    with pytest.raises(TypeError, match="list of member names"):
        itf.requires("store", shape="get")


def test_a_present_role_selects_the_test(session):
    assert decide(session, Requirement("store")).selected


def test_a_missing_role_deselects_with_a_reason_naming_the_roles(session):
    decision = decide(session, Requirement("command"))
    assert not decision.selected
    assert decision.reason == "target has no role 'command'; roles: reader, slim, store"


def test_another_contract_deselects(session):
    decision = decide(session, Requirement("store", contract="kv.view"))
    assert not decision.selected
    assert "is 'kv.store', the test requires 'kv.view'" in decision.reason
    assert decide(session, Requirement("store", contract="kv.store")).selected


def test_missing_members_deselect(session):
    assert decide(session, Requirement("reader", shape=("read",))).selected
    decision = decide(session, Requirement("slim", shape=("read",)))
    assert not decision.selected
    assert "lacks member(s): read" in decision.reason


def test_a_major_the_factory_does_not_offer_deselects(tmp_path):
    session = Session(
        [kv_parts],
        target="capabilities:\n  store: local.store\n  reader: local.view_v1\n",
        plan_only=True,
        run_dir=tmp_path / "run",
    ).resolve()
    assert decide(session, Requirement("reader", "kv.view", None, None, 1)).selected
    decision = decide(session, Requirement("reader", "kv.view", None, None, 2))
    assert not decision.selected and "offers @1, the test requires @2" in decision.reason


def test_a_scope_is_checked_instead_of_the_root(tmp_path):
    session = Session(
        [kv_parts],
        target="capabilities:\n  store: local.store\nscopes:\n  gw:\n    capabilities:\n      other: local.store\n",
        plan_only=True,
        run_dir=tmp_path / "run",
    ).resolve()
    assert decide(session, Requirement("other", scope="gw")).selected
    assert not decide(session, Requirement("other")).selected
    decision = decide(session, Requirement("store", scope="nowhere"))
    assert decision.reason == "target has no scope 'nowhere'"


def test_every_requirement_must_hold(session):
    assert not decide(session, Requirement("store"), Requirement("command")).selected


# ---- the reasons, word for word --------------------------------------------------------------------------------


def plan_of(session):
    return session.target_plan


def reason(session, requirement, scope="__itf_root__", majors=None):
    from score.itf.core.gating import evaluate

    return evaluate(requirement, plan_of(session), scope, majors)


def test_each_deselection_names_the_role_the_factory_and_what_differs(session):
    assert reason(session, Requirement("store", contract="kv.view")).reason == (
        "target.store (local.store) is 'kv.store', the test requires 'kv.view'"
    )
    assert reason(session, Requirement("slim", shape=("read", "peek", "zap"))).reason == (
        "target.slim (local.slim_view) lacks member(s): read, zap"
    )
    assert reason(session, Requirement("reader", major=3), majors={"local.view": 1}).reason == (
        "target.reader (local.view) offers @1, the test requires @3"
    )


def test_a_required_major_is_unknown_when_the_factory_does_not_declare_one(session):
    assert reason(session, Requirement("reader", major=3)).status == "unknown"
    assert reason(session, Requirement("reader", major=3), majors={"local.other": 1}).status == "unknown"
    assert reason(session, Requirement("reader", major=1), majors={"local.view": 1}).selected


def test_the_first_failing_rule_decides_and_a_passing_requirement_has_no_reason(session):
    both = Requirement("store", contract="kv.view", shape=("zap",))
    assert "requires 'kv.view'" in reason(session, both).reason
    ok = reason(session, Requirement("reader", contract="kv.view", shape=("read",)))
    assert (ok.selected, ok.reason) == (True, "")


class WaitingConsole(Protocol):
    __contract__ = "exec.console"

    def wait_for(self, pattern: str, timeout: float = 30, *, since: int = 0, regex: bool = False) -> str | None: ...


class CompatibleConsole:
    def wait_for(self, pattern, timeout=30, *, since=0, regex=False, extra=None): ...


class MissingKeywordsConsole:
    def wait_for(self, pattern, timeout=30): ...


class RequiredExtraConsole:
    def wait_for(self, pattern, timeout=30, *, since=0, regex=False, extra): ...


@pytest.mark.parametrize(
    "offering, selected",
    [(CompatibleConsole, True), (MissingKeywordsConsole, False), (RequiredExtraConsole, False)],
)
def test_protocol_requirements_check_supported_calls_without_constructing_a_target(offering, selected):
    from score.itf.core.gating import evaluate
    from score.itf.core.octo import shape_of

    requirement = itf.requires("console", shape=WaitingConsole).requirement
    node = SimpleNamespace(
        provider="example.console", contract="exec.console", gives=shape_of(offering, signatures=True)
    )
    plan = SimpleNamespace(names=lambda scope: ("console",), node=lambda ref: node)

    decision = evaluate(requirement, plan, "__itf_root__")

    assert requirement.contract == "exec.console"
    assert decision.selected is selected
    if not selected:
        assert "wait_for" in decision.reason and "signature" in decision.reason


def test_preflight_groups_exact_profiles_without_hiding_partial_compatibility(session):
    basic = Requirement("reader", contract="kv.view", shape=("read",))
    extended = Requirement("reader", contract="kv.view", shape=("read", "unsupported"))
    decisions = session.select({"basic": (basic,), "extended_a": (extended,), "extended_b": (extended,)})

    report = session.preflight_report
    assert report.decisions == decisions
    assert len(report.groups) == 1
    group = report.groups[0]
    assert (group.role, group.contract, group.status) == ("reader", "kv.view", "partial")
    assert len(group.profiles) == 2
    blocked = report.blocking
    assert len(blocked) == 1
    assert blocked[0].tests == ("extended_a", "extended_b")
    assert blocked[0].decision.status == "incompatible"
    assert blocked[0].decision.diagnostics[0].code == "SHAPE_MISSING_MEMBER"
    assert decisions["basic"].selected and not decisions["extended_a"].selected
    assert kv_parts.EVENTS == []


def test_an_absent_role_does_not_hide_another_api_deviation(session):
    decisions = session.select({"test": (Requirement("missing"), Requirement("reader", shape=("unsupported",)))})
    assert not decisions["test"].selected
    assert len(session.preflight_report.groups) == 2
    assert session.preflight_report.blocking[0].requirement.role == "reader"


def test_preflight_is_deterministic_and_normalizes_the_root_scope(session):
    from score.itf.core.engine.scopes import ROOT

    first = Requirement("reader", contract="kv.view", shape=("read",))
    second = Requirement("reader", contract="kv.view", shape=("unsupported",), scope=ROOT)
    requirements = {"test_b": (first, second), "test_a": (replace(first, scope=ROOT),)}
    session.select(requirements)
    before = session.preflight_report.to_json()
    session.select(dict(reversed(list(requirements.items()))))
    assert session.preflight_report.to_json() == before
    assert len(session.preflight_report.groups[0].profiles) == 2
    assert next(
        profile for profile in session.preflight_report.groups[0].profiles if profile.decision.selected
    ).tests == (
        "test_a",
        "test_b",
    )


def test_explicit_major_differences_are_not_applicable_but_missing_majors_are_unknown(session):
    from score.itf.core.gating import preflight

    requirements = {
        "v1": (Requirement("reader", "kv.view", major=1),),
        "v2": (Requirement("reader", "kv.view", major=2),),
    }
    report = preflight(requirements, session.target_plan, {"local.view": 1})
    assert report.decisions["v1"].selected
    assert report.decisions["v2"].status == "not_applicable"
    assert not report.blocking
    assert {group.major for group in report.groups} == {1, 2}
    report = preflight(requirements, session.target_plan)
    assert not any(decision.selected for decision in report.decisions.values())
    assert len(report.blocking) == 2
    assert all(profile.decision.status == "unknown" for profile in report.blocking)


def test_strict_callable_requirements_report_uninspectable_methods_as_unknown():
    from score.itf.core.gating import evaluate
    from score.itf.core.octo import Member, Shape

    node = SimpleNamespace(
        provider="example.console",
        contract="exec.console",
        gives=Shape(
            members=frozenset({Member("wait_for", kind="call")}),
        ),
    )
    plan = SimpleNamespace(names=lambda scope: ("console",), node=lambda ref: node)
    decision = evaluate(itf.requires("console", shape=WaitingConsole).requirement, plan, "__itf_root__")
    assert not decision.selected and decision.status == "unknown"
    assert "metadata is unavailable" in decision.reason
