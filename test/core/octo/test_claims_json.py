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
"""Canonical claim JSON: every claim type, and `Shape`/`Need`/`Member`, round-trip through
`to_json`/`from_json` byte-for-byte equal. This is the schema
the YAML frontend and `claims.json` artifact both target."""

from __future__ import annotations

from score.itf.core.octo import (
    AssumeClaim,
    BindingClaim,
    CapabilityContractClaim,
    GoalClaim,
    Member,
    Need,
    NodeClaim,
    ProviderClaim,
    RelationClaim,
    Shape,
    ShapeExpectationClaim,
    StateContractClaim,
    claim_from_json,
    claim_to_json,
    claims_from_json,
    claims_to_json,
)


def test_member_round_trips():
    member = Member("close", kind="call", signature="() -> None")
    assert Member.from_json(member.to_json()) == member


def test_shape_round_trips():
    shape = Shape(members=frozenset({Member("run"), Member("close")}), protocols=frozenset({"ctx_mgr"}))
    assert Shape.from_json(shape.to_json()) == shape


def test_need_round_trips():
    need = Need("world", "world.handle", expected=Shape.of("teardown"))
    assert Need.from_json(need.to_json()) == need


def test_capability_contract_claim_round_trips():
    claim = CapabilityContractClaim(
        token="itf.capabilities.exec.shell",
        gives=Shape.of("run", "close"),
        needs=(Need("world", "world.handle"),),
        origin="plugin",
    )
    assert CapabilityContractClaim.from_json(claim.to_json()) == claim


def test_provider_claim_round_trips():
    claim = ProviderClaim(
        name="fake_shell.session",
        implements="itf.capabilities.exec.shell",
        gives=Shape.of("run"),
        needs=(Need("world", "world.handle"),),
        impl="fake_shell.providers:make_session",
        origin="plugin",
    )
    assert ProviderClaim.from_json(claim.to_json()) == claim


def test_node_claim_round_trips():
    claim = NodeClaim(
        scope="main",
        name="shell",
        contract="itf.capabilities.exec.shell",
        using="fake_shell.session",
        bind=(("world", "world"),),
        config=(("timeout", 5),),
        origin="policy",
    )
    assert NodeClaim.from_json(claim.to_json()) == claim


def test_binding_claim_round_trips():
    claim = BindingClaim(scope="main", name="shell", bind=(("world", "world"),), origin="policy")
    assert BindingClaim.from_json(claim.to_json()) == claim


def test_state_contract_claim_round_trips():
    claim = StateContractClaim(
        token="itf.states.shell.open",
        impl="fake_shell.open_session",
        probe="fake_shell.is_session_open",
        requires=frozenset({"itf.states.network.reachable"}),
        invalidates=frozenset(),
        also_delivers=frozenset({"ready"}),
        uses=(Need("shell", "itf.capabilities.exec.shell"),),
        scope="",
        origin="plugin",
    )
    assert StateContractClaim.from_json(claim.to_json()) == claim


def test_goal_claim_round_trips():
    claim = GoalClaim(
        scope="main", states=frozenset({"itf.states.shell.open", "itf.states.image.present"}), origin="policy"
    )
    assert GoalClaim.from_json(claim.to_json()) == claim


def test_relation_claim_round_trips():
    claim = RelationClaim(
        state="itf.states.shell.open",
        adds_requires=frozenset({"itf.states.network.reachable"}),
        adds_invalidates=frozenset({"itf.states.image.present"}),
        scope="main",
        origin="policy",
    )
    assert RelationClaim.from_json(claim.to_json()) == claim


def test_assume_claim_round_trips():
    claim = AssumeClaim(
        scope="main", token="itf.states.network.reachable", owner="lab", reason="managed externally", origin="policy"
    )
    assert AssumeClaim.from_json(claim.to_json()) == claim


def test_shape_expectation_claim_round_trips():
    claim = ShapeExpectationClaim(
        contract="itf.capabilities.descriptor.endpoint", shape=Shape.of("host", "port"), origin="policy"
    )
    assert ShapeExpectationClaim.from_json(claim.to_json()) == claim


def test_claim_to_from_json_dispatches_on_kind():
    claim = GoalClaim(scope="main", states=frozenset({"itf.states.shell.open"}), origin="policy")
    data = claim_to_json(claim)
    assert data["_kind"] == "GoalClaim"
    assert claim_from_json(data) == claim


def test_claims_to_from_json_round_trips_a_mixed_set():
    claims = frozenset(
        {
            GoalClaim(scope="main", states=frozenset({"itf.states.shell.open"}), origin="policy"),
            AssumeClaim(scope="main", token="itf.states.network.reachable", owner="lab", reason="", origin="policy"),
            NodeClaim(scope="main", name="shell", using="fake_shell.session", origin="plugin"),
        }
    )
    assert claims_from_json(claims_to_json(claims)) == claims
