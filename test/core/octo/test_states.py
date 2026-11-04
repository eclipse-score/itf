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
"""Gate 2 tests: which actions are needed, in which order, with which slots.

Non-domain reference vocabulary: a web shop. States: db_up, schema_migrated, cache_warm,
api_serving, data_seeded. Contracts: db.pool, cache.client, http.api.
"""

from __future__ import annotations

import pytest

import dataclasses

from score.itf.core.octo import (
    CAPABILITY,
    CapabilityContractClaim,
    GoalClaim,
    Kind,
    Need,
    NodeClaim,
    ProviderClaim,
    RelationClaim,
    Shape,
    StateContractClaim,
    TargetPlan,
    resolve_actions,
    resolve_target,
)
from score.itf.core.octo.std import capability as capabilities


def _empty_target():
    return TargetPlan(nodes=(), construction_order=(), aliases=(), seams=())


def _shop_target():
    contracts = frozenset({CapabilityContractClaim(token="cache.client", gives=Shape.of("get"))})
    providers = frozenset({ProviderClaim(name="acme.cache", implements="cache.client", impl="m:cache")})
    nodes = frozenset({NodeClaim(scope="shop", name="cache", contract="cache.client", using="acme.cache")})
    res = resolve_target(contracts | providers | nodes)
    assert res.ok(), res.diagnostics
    return res.plan


def test_A_2_1_every_temporal_edge_carries_a_state():
    target = _empty_target()
    db_up = StateContractClaim(token="db_up", impl="m:db_up", probe="m:p_db_up", scope="shop")
    schema = StateContractClaim(
        token="schema_migrated", impl="m:schema", probe="m:p_schema", scope="shop", requires=frozenset({"db_up"})
    )
    goal = GoalClaim(scope="shop", states=frozenset({"schema_migrated"}))
    res = resolve_actions(frozenset({db_up, schema, goal}), target)
    assert res.ok(), res.diagnostics
    assert len(res.plan.edges) >= 1
    for e in res.plan.edges:
        assert e.state


def test_A_2_2_unreachable_required_state_named():
    target = _empty_target()
    schema = StateContractClaim(
        token="schema_migrated", impl="m:schema", probe="m:p_schema", scope="shop", requires=frozenset({"db_up"})
    )
    goal = GoalClaim(scope="shop", states=frozenset({"schema_migrated"}))
    res = resolve_actions(frozenset({schema, goal}), target)
    assert not res.ok()
    d = [x for x in res.diagnostics if x.code == "STATE_UNREACHABLE"]
    assert len(d) == 1
    assert d[0].subject == "state:db_up"


def test_A_2_3_invalidates_forces_order_requires_alone_does_not():
    target = _shop_target()
    db_up = StateContractClaim(token="db_up", impl="m:db_up", probe="m:p_db_up", scope="shop")
    cache_warm = StateContractClaim(
        token="cache_warm",
        impl="m:cache_warm",
        probe="m:p_cache_warm",
        scope="shop",
        requires=frozenset({"db_up"}),
        uses=(Need(slot="client", contract="cache.client", expected=Shape.of("get")),),
    )
    schema_with = StateContractClaim(
        token="schema_migrated",
        impl="m:schema",
        probe="m:p_schema",
        scope="shop",
        requires=frozenset({"db_up"}),
        invalidates=frozenset({"cache_warm"}),
    )
    goal = GoalClaim(scope="shop", states=frozenset({"cache_warm", "schema_migrated"}))

    res = resolve_actions(frozenset({db_up, cache_warm, schema_with, goal}), target)
    assert res.ok(), res.diagnostics
    order = [s.key for s in res.plan.steps]
    assert order.index("shop:schema_migrated") < order.index("shop:cache_warm")

    schema_without = StateContractClaim(
        token="schema_migrated", impl="m:schema", probe="m:p_schema", scope="shop", requires=frozenset({"db_up"})
    )
    res2 = resolve_actions(frozenset({db_up, cache_warm, schema_without, goal}), target)
    assert res2.ok(), res2.diagnostics
    between = [e for e in res2.plan.edges if {e.before, e.after} == {"shop:cache_warm", "shop:schema_migrated"}]
    assert between == []


def test_A_2_4_mutual_invalidation_ambiguous_not_ordered():
    target = _empty_target()
    a = StateContractClaim(token="a_state", impl="m:a", probe="m:pa", scope="shop", invalidates=frozenset({"b_state"}))
    b = StateContractClaim(token="b_state", impl="m:b", probe="m:pb", scope="shop", invalidates=frozenset({"a_state"}))
    goal = GoalClaim(scope="shop", states=frozenset({"a_state", "b_state"}))
    res = resolve_actions(frozenset({a, b, goal}), target)
    assert not res.ok()
    assert res.diagnostics[0].code == "ORDER_AMBIGUOUS"
    assert res.plan is None


def test_A_2_5_relation_claim_from_other_origin_changes_order():
    target = _empty_target()
    db_up = StateContractClaim(token="db_up", impl="m:db_up", probe="m:p_db_up", scope="shop")
    api_serving = StateContractClaim(token="api_serving", impl="m:api", probe="m:p_api", scope="shop")
    goal = GoalClaim(scope="shop", states=frozenset({"db_up", "api_serving"}))

    res_no_relation = resolve_actions(frozenset({db_up, api_serving, goal}), target)
    assert res_no_relation.ok(), res_no_relation.diagnostics
    no_edge = [e for e in res_no_relation.plan.edges if {e.before, e.after} == {"shop:db_up", "shop:api_serving"}]
    assert no_edge == []

    relation = RelationClaim(state="api_serving", adds_requires=frozenset({"db_up"}), origin="policy")
    res_with = resolve_actions(frozenset({db_up, api_serving, goal, relation}), target)
    assert res_with.ok(), res_with.diagnostics
    order = [s.key for s in res_with.plan.steps]
    assert order.index("shop:db_up") < order.index("shop:api_serving")

    # duplicates are not a conflict
    relation2 = RelationClaim(state="api_serving", adds_requires=frozenset({"db_up"}), origin="pack")
    res_dup = resolve_actions(frozenset({db_up, api_serving, goal, relation, relation2}), target)
    assert res_dup.ok(), res_dup.diagnostics


def test_A_2_6_observed_states_pruned_and_re_delivered_after_invalidator():
    target = _empty_target()
    db_up = StateContractClaim(token="db_up", impl="m:db_up", probe="m:p_db_up", scope="shop")
    cache_warm = StateContractClaim(
        token="cache_warm", impl="m:cache_warm", probe="m:p_cache_warm", scope="shop", requires=frozenset({"db_up"})
    )
    schema = StateContractClaim(
        token="schema_migrated",
        impl="m:schema",
        probe="m:p_schema",
        scope="shop",
        requires=frozenset({"db_up"}),
        invalidates=frozenset({"cache_warm"}),
    )
    goal = GoalClaim(scope="shop", states=frozenset({"cache_warm", "schema_migrated"}))
    observed = frozenset({"shop:db_up", "shop:cache_warm"})

    res = resolve_actions(frozenset({db_up, cache_warm, schema, goal}), target, observed_states=observed)
    assert res.ok(), res.diagnostics
    keys = [s.key for s in res.plan.steps]
    assert "shop:db_up" not in keys
    assert "shop:schema_migrated" in keys
    assert "shop:cache_warm" in keys
    assert keys.index("shop:schema_migrated") < keys.index("shop:cache_warm")

    everything = observed | {"shop:schema_migrated"}
    res_all = resolve_actions(frozenset({db_up, cache_warm, schema, goal}), target, observed_states=everything)
    assert res_all.ok(), res_all.diagnostics
    assert res_all.plan.steps == ()


def test_A_2_7_uses_binds_against_target_and_fails_before_execution():
    target = _shop_target()
    cache_warm = StateContractClaim(
        token="cache_warm",
        impl="m:cache_warm",
        probe="m:p_cache_warm",
        scope="shop",
        uses=(Need(slot="client", contract="cache.client", expected=Shape.of("get")),),
    )
    goal = GoalClaim(scope="shop", states=frozenset({"cache_warm"}))
    res = resolve_actions(frozenset({cache_warm, goal}), target)
    assert res.ok(), res.diagnostics
    step = res.plan.steps[0]
    assert dict(step.uses)["client"] == "shop.cache"

    unsatisfied = StateContractClaim(
        token="cache_warm",
        impl="m:cache_warm",
        probe="m:p_cache_warm",
        scope="shop",
        uses=(Need(slot="client", contract="http.api"),),
    )
    res2 = resolve_actions(frozenset({unsatisfied, goal}), target)
    assert not res2.ok()
    assert res2.diagnostics[0].code == "USES_UNSATISFIED"
    assert res2.plan is None

    served = StateContractClaim(token="served", impl="m:serve", scope="shop", requires=frozenset({"cache_warm"}))
    res3 = resolve_actions(
        frozenset({unsatisfied, served, GoalClaim(scope="shop", states=frozenset({"served"}))}), target
    )
    assert dict(res3.diagnostics[0].evidence) == {
        "action": "m:cache_warm",
        "contract": "http.api",
        "elsewhere": "",
        "required_by": "shop:served",
        "scope": "shop",
        "slot": "client",
    }


def test_A_2_8_third_kind_through_same_generic_machinery():
    """A third kind (a replica of capability): its ref is shared with
    CAPABILITY, so it resolves through the exact same capabilities module with no core change."""
    REPLICA = Kind(
        name="replica",
        ref="contract-to-node",
        roles=frozenset({"needs"}),
        idempotent=True,
        permanent=False,
        reversible=False,
        realization="construct",
        evidence="probe",
        scoped=False,
        identity="token",
    )
    contracts = frozenset({CapabilityContractClaim(token="artifact.image")})
    providers = frozenset({ProviderClaim(name="builder.image", implements="artifact.image", impl="m:build")})
    nodes = frozenset({NodeClaim(scope="", name="release", contract="artifact.image", using="builder.image")})
    plan, diags = capabilities.resolve_contract_to_node(REPLICA, contracts | providers | nodes)
    assert not diags, diags
    assert len(plan.nodes) == 1
    assert plan.nodes[0].provider == "builder.image"


def _device(app_requires):
    s = lambda tok, **kw: StateContractClaim(
        token=tok, impl=f"m:{tok}", probe=f"m:p_{tok}", scope="d", **{k: frozenset(v) for k, v in kw.items()}
    )
    return {
        s("itf.states.network.reachable"),
        s("itf.states.shell.open", requires={"itf.states.network.reachable"}),
        s(
            "itf.states.image.present",
            requires={"itf.states.network.reachable"},
            invalidates={"itf.states.shell.open", "itf.states.application.running"},
        ),
        s("itf.states.application.running", requires=app_requires),
        GoalClaim(
            scope="d",
            states=frozenset({"itf.states.shell.open", "itf.states.image.present", "itf.states.application.running"}),
        ),
    }


@pytest.mark.parametrize(
    "app_requires", [{"itf.states.shell.open"}, {"itf.states.shell.open", "itf.states.image.present"}]
)
def test_A_2_3_destroyer_runs_before_the_producer_of_a_state_still_needed(app_requires):
    res = resolve_actions(frozenset(_device(app_requires)), _empty_target())
    assert res.ok(), res.diagnostics
    order = [s.key for s in res.plan.steps]
    assert order == [
        "d:itf.states.network.reachable",
        "d:itf.states.image.present",
        "d:itf.states.shell.open",
        "d:itf.states.application.running",
    ]
    assert any(e.reason == "invalidates" and e.before == "d:itf.states.image.present" for e in res.plan.edges)


def test_an_action_is_held_to_the_shape_its_uses_expect_of_the_bound_node():
    from score.itf.core.octo import Need, Shape

    provider = ProviderClaim(name="acme.pool", implements="db.pool", gives=Shape.of("query"), impl="m:pool")
    target = resolve_target({provider, NodeClaim(scope="d", name="pool", contract="db.pool")}).plan
    assert target.node("d.pool").gives == Shape.of("query")

    def migrate(*members):
        return {
            StateContractClaim(
                token="migrated", impl="m:migrate", scope="d", uses=(Need("pool", "db.pool", Shape.of(*members)),)
            ),
            GoalClaim(scope="d", states=frozenset({"migrated"})),
        }

    assert resolve_actions(migrate("query"), target).ok()
    res = resolve_actions(migrate("query", "execute"), target)
    assert [(d.code, d.subject, d.gate) for d in res.diagnostics] == [
        ("SHAPE_MISSING_MEMBER", "d:migrated#pool", 2),
    ]


def test_collapsed_contracts_keep_each_probe_for_their_own_state():
    from score.itf.core.octo import resolve_actions, resolve_target

    target = resolve_target(
        frozenset(
            {
                CapabilityContractClaim(token="link.handle", gives=Shape.of("send")),
                ProviderClaim(name="p.link", implements="link.handle", impl="m:make"),
                NodeClaim(scope="s", name="link", contract="link.handle", using="p.link"),
            }
        )
    )
    uses = (Need(slot="link", contract="link.handle", expected=Shape.of("send")),)
    init = frozenset(
        {
            StateContractClaim(token="session.open", impl="m:connect", probe="m:session_probe", uses=uses),
            StateContractClaim(token="peer.reachable", impl="m:connect", probe="m:peer_probe", uses=uses),
            GoalClaim(scope="s", states=frozenset({"session.open", "peer.reachable"})),
        }
    )
    actions = resolve_actions(init, target.plan)
    assert actions.ok(), actions.diagnostics
    [step] = actions.plan.steps
    assert dict(step.probes) == {"s:peer.reachable": "m:peer_probe", "s:session.open": "m:session_probe"}
    assert type(actions.plan).from_json(actions.plan.to_json()) == actions.plan


def _two_caches():
    contracts = frozenset({CapabilityContractClaim(token="cache.client", gives=Shape.of("get"))})
    providers = frozenset({ProviderClaim(name="acme.cache", implements="cache.client", impl="m:cache")})
    nodes = frozenset(
        {
            NodeClaim(scope="shop", name="client", contract="cache.client", using="acme.cache"),
            NodeClaim(scope="shop", name="other", contract="cache.client", using="acme.cache"),
        }
    )
    res = resolve_target(contracts | providers | nodes)
    assert res.ok(), res.diagnostics
    return res.plan


def _warm(**kw):
    return StateContractClaim(
        token="cache_warm",
        impl="m:cache_warm",
        scope="shop",
        uses=(Need(slot="client", contract="cache.client", expected=Shape.of("get")),),
        **kw,
    )


def test_a_slot_is_not_filled_by_the_role_that_carries_its_name():
    goal = GoalClaim(scope="shop", states=frozenset({"cache_warm"}))
    res = resolve_actions(frozenset({_warm(), goal}), _two_caches())
    assert [(d.code, d.subject) for d in res.diagnostics] == [("USES_AMBIGUOUS", "shop:cache_warm#client")]
    assert [v for k, v in res.diagnostics[0].evidence] == ["shop.client", "shop.other"]


def test_an_explicit_bind_fills_the_slot_and_is_checked():
    goal = GoalClaim(scope="shop", states=frozenset({"cache_warm"}))
    res = resolve_actions(frozenset({_warm(bind=(("client", "other"),)), goal}), _two_caches())
    assert res.ok(), res.diagnostics
    assert dict(res.plan.steps[0].uses)["client"] == "shop.other"
    for role, reason in (("nothing", "no such role"), ("client", None)):
        bad = resolve_actions(frozenset({_warm(bind=(("client", role),)), goal}), _two_caches())
        assert bad.ok() == (reason is None), bad.diagnostics
        if reason:
            assert [d.code for d in bad.diagnostics] == ["USES_BIND_INVALID"]
            assert reason in dict(bad.diagnostics[0].evidence)["reason"]
