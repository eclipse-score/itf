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
"""Gate 2 tests for assumptions: `assume()` suppresses a producer without evidence, and
the plan records exactly which states were taken on faith.

Same non-domain vocabulary as test_states.py: a web shop.
"""

from __future__ import annotations

from score.itf.core.octo import (
    AssumeClaim,
    GoalClaim,
    StateContractClaim,
    TargetPlan,
    resolve_actions,
)


def _empty_target():
    return TargetPlan(nodes=(), construction_order=(), aliases=(), seams=())


def test_A_2_9_assume_suppresses_the_producer_but_the_plan_records_it():
    target = _empty_target()
    db_up = StateContractClaim(token="db_up", impl="m:db_up", probe="m:p_db_up", scope="shop")
    schema = StateContractClaim(
        token="schema_migrated", impl="m:schema", probe="m:p_schema", scope="shop", requires=frozenset({"db_up"})
    )
    goal = GoalClaim(scope="shop", states=frozenset({"schema_migrated"}))
    assume = AssumeClaim(
        scope="shop", token="db_up", owner="dba_team", reason="provisioned by terraform", origin="policy"
    )

    res = resolve_actions(frozenset({db_up, schema, goal, assume}), target)
    assert res.ok(), res.diagnostics
    keys = [s.key for s in res.plan.steps]
    assert "shop:db_up" not in keys
    assert "shop:schema_migrated" in keys
    assert res.plan.assumed == ("shop:db_up",)


def test_A_2_9_global_assume_applies_in_every_scope_that_touches_it():
    target = _empty_target()
    db_up = StateContractClaim(token="db_up", impl="m:db_up", probe="m:p_db_up", scope="")
    schema = StateContractClaim(
        token="schema_migrated", impl="m:schema", probe="m:p_schema", scope="", requires=frozenset({"db_up"})
    )
    goal_a = GoalClaim(scope="a", states=frozenset({"schema_migrated"}))
    goal_b = GoalClaim(scope="b", states=frozenset({"schema_migrated"}))
    assume = AssumeClaim(scope="", token="db_up", owner="platform", reason="shared external database")

    res = resolve_actions(frozenset({db_up, schema, goal_a, goal_b, assume}), target)
    assert res.ok(), res.diagnostics
    keys = {s.key for s in res.plan.steps}
    assert "a:db_up" not in keys and "b:db_up" not in keys
    assert set(res.plan.assumed) == {"a:db_up", "b:db_up"}


def test_A_2_9_assumed_state_needs_no_producer_at_all():
    target = _empty_target()
    api_serving = StateContractClaim(
        token="api_serving", impl="m:api", probe="m:p_api", scope="shop", requires=frozenset({"license_active"})
    )
    goal = GoalClaim(scope="shop", states=frozenset({"api_serving"}))
    assume = AssumeClaim(scope="shop", token="license_active", owner="legal", reason="verified out of band")

    res = resolve_actions(frozenset({api_serving, goal, assume}), target)
    assert res.ok(), res.diagnostics
    assert [s.key for s in res.plan.steps] == ["shop:api_serving"]
    assert res.plan.assumed == ("shop:license_active",)


def test_A_2_9_request_level_assumed_states_param_needs_no_claim():
    target = _empty_target()
    db_up = StateContractClaim(token="db_up", impl="m:db_up", probe="m:p_db_up", scope="shop")
    schema = StateContractClaim(
        token="schema_migrated", impl="m:schema", probe="m:p_schema", scope="shop", requires=frozenset({"db_up"})
    )
    goal = GoalClaim(scope="shop", states=frozenset({"schema_migrated"}))

    res = resolve_actions(frozenset({db_up, schema, goal}), target, assumed_states=frozenset({"shop:db_up"}))
    assert res.ok(), res.diagnostics
    keys = [s.key for s in res.plan.steps]
    assert "shop:db_up" not in keys
    assert res.plan.assumed == ("shop:db_up",)


def test_A_2_9_an_assumed_state_still_destroyed_by_an_active_step_is_re_delivered():
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
    assume = AssumeClaim(scope="shop", token="cache_warm", owner="ops", reason="warmed on boot")

    res = resolve_actions(frozenset({db_up, cache_warm, schema, goal, assume}), target)
    assert res.ok(), res.diagnostics
    keys = [s.key for s in res.plan.steps]
    assert "shop:cache_warm" in keys  # schema_migrated destroys it, so it must be re-delivered
    assert "shop:cache_warm" not in res.plan.assumed  # it ran; nothing was taken on faith


def test_A_2_10_conflicting_assumptions_at_equal_precedence_are_reported():
    target = _empty_target()
    db_up = StateContractClaim(token="db_up", impl="m:db_up", probe="m:p_db_up", scope="shop")
    goal = GoalClaim(scope="shop", states=frozenset({"db_up"}))
    a = AssumeClaim(scope="shop", token="db_up", owner="team_a", reason="a", origin="policy")
    b = AssumeClaim(scope="shop", token="db_up", owner="team_b", reason="b", origin="policy")

    res = resolve_actions(frozenset({db_up, goal, a, b}), target)
    assert not res.ok()
    assert res.diagnostics[0].code == "ASSUMPTION_CONFLICT"
    assert res.diagnostics[0].subject == "state:db_up"
