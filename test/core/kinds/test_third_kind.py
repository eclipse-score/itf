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
"""The extension surface: kinds and relations are
checked at construction; claims are admitted by the relation that owns their type; a relation's
failures come back as diagnostics; and a third kind plugs in exactly as the two standard ones do."""

from __future__ import annotations

import pytest

from score.itf.core.octo import (
    CAPABILITY,
    RELATIONS,
    STATE,
    Diagnostic,
    GoalClaim,
    Kind,
    KindSetInvalid,
    NodeClaim,
    Octo,
    ProviderClaim,
    Relation,
    StateContractClaim,
    TargetPlan,
    resolve_actions,
    resolve_target,
)
from score.itf.core.octo.std import state

# Unscoped, never destroyed, nothing to borrow: a session-wide checklist of facts.
MILESTONE = Kind(
    name="milestone",
    ref="checklist",
    roles=frozenset({"needs", "produces"}),
    idempotent=True,
    permanent=True,
    reversible=False,
    realization="invoke",
    evidence="none",
    scoped=False,
    identity="token",
)

EMPTY_TARGET = TargetPlan(nodes=(), construction_order=(), aliases=(), seams=())

# A relation may reuse an existing algorithm: this one runs Gate 2's against an empty target.
CHECKLIST = Relation(
    ref="checklist",
    claim_types=(StateContractClaim, GoalClaim),
    resolve=lambda kind, claims, **options: state.resolve_condition_to_producer(kind, claims, EMPTY_TARGET, **options),
    codes=state.CODES,
    edge_reasons=frozenset({"delivers-requires", "invalidates"}),
)


@pytest.mark.parametrize(
    "kinds, relations, message",
    [
        ((), RELATIONS, "at least one kind"),
        ((CAPABILITY, CAPABILITY), RELATIONS, "unique"),
        ((CAPABILITY,), (), "no relation for ref 'contract-to-node'"),
        ((STATE,), RELATIONS, "uses units of an earlier kind"),
        ((STATE, CAPABILITY), RELATIONS, "uses units of an earlier kind"),
        ((CAPABILITY, STATE, MILESTONE), RELATIONS + (CHECKLIST,), "owned by both"),
        ((CAPABILITY,), RELATIONS + RELATIONS[:1], "two relations share a ref"),
    ],
)
def test_an_inconsistent_kind_set_is_rejected_at_construction(kinds, relations, message):
    with pytest.raises(KindSetInvalid, match=message):
        Octo(kinds, relations)


def test_claims_are_admitted_by_the_kind_that_owns_their_type():
    res = resolve_target([GoalClaim(scope="s", states=frozenset({"x"})), object()])
    assert {(d.code, d.subject, d.gate) for d in res.diagnostics} == {
        ("CLAIM_WRONG_GATE", "s:goal", 1),
        ("UNKNOWN_KIND", "object", 1),
    }
    # with no state kind registered, nothing owns a GoalClaim
    res = Octo((CAPABILITY,), RELATIONS).resolve(CAPABILITY, [GoalClaim(scope="s", states=frozenset({"x"}))])
    assert [d.code for d in res.diagnostics] == ["UNKNOWN_KIND"]


def _broken(resolve):
    kind = Kind(
        name="broken",
        ref="broken",
        roles=frozenset(),
        idempotent=True,
        permanent=True,
        reversible=False,
        realization="invoke",
        evidence="none",
        scoped=False,
        identity="token",
    )
    return kind, Octo((kind,), (Relation(ref="broken", claim_types=(), resolve=resolve, codes=frozenset({"OWN"})),))


def test_a_relation_failure_is_reported_never_raised():
    def boom(kind, claims):
        raise RuntimeError("bug in the relation")

    kind, octo = _broken(boom)
    assert [(d.code, d.subject, d.evidence) for d in octo.resolve(kind, []).diagnostics] == [
        ("RELATION_FAILED", "broken", (("error", "RuntimeError: bug in the relation"),)),
    ]


def test_a_relation_may_only_emit_codes_it_declared():
    kind, octo = _broken(lambda kind, claims: (None, (Diagnostic("OWN", "x", 1), Diagnostic("ALIEN", "y", 1))))
    assert [(d.code, d.evidence) for d in octo.resolve(kind, []).diagnostics] == [
        ("OWN", ()),
        ("RELATION_FAILED", (("undeclared_code", "ALIEN"),)),
    ]
    assert "OWN" in octo.codes


def test_plans_record_the_kind_set():
    target = resolve_target(
        [
            ProviderClaim(name="p", implements="c", impl="m:p"),
            NodeClaim(scope="s", name="n", contract="c"),
        ]
    )
    actions = resolve_actions([], target.plan)
    assert target.plan.kinds == actions.plan.kinds == ("capability", "state")
    assert TargetPlan.from_json(target.plan.to_json()) == target.plan


def _checklist():
    step = lambda tok, **kw: StateContractClaim(token=tok, impl=f"m:{tok}", **{k: frozenset(v) for k, v in kw.items()})
    return [
        step("stocked"),
        step("priced", requires={"stocked"}),
        step("opened", requires={"priced"}),
        step("swept", invalidates={"stocked"}),
        GoalClaim(scope="east", states=frozenset({"opened", "swept"})),
        GoalClaim(scope="west", states=frozenset({"opened", "swept"})),
    ]


def test_a_third_kind_runs_through_the_same_resolver():
    state = resolve_actions(_checklist(), EMPTY_TARGET).plan
    milestone = Octo((MILESTONE,), (CHECKLIST,)).resolve(MILESTONE, _checklist())
    assert milestone.ok(), milestone.diagnostics
    plan = milestone.plan

    # scoped=False: one session-wide fact per token, where the state kind keeps one per scope
    # (collapsed into one step, since both instances are the same call)
    assert ("east:stocked", "west:stocked") in [s.delivers for s in state.steps]
    assert sorted(s.delivers for s in plan.steps) == [(":opened",), (":priced",), (":stocked",), (":swept",)]
    # no "destroys" role: an invalidation orders nothing
    assert any(e.reason == "invalidates" for e in state.edges)
    assert {e.reason for e in plan.edges} == {"delivers-requires"}
    assert plan.kinds == ("milestone",)
