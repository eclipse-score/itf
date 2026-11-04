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
"""The standard kinds: capability (what must exist) and state (what must happen).

Built only on OCTO's public extension surface — `Kind` + `Relation` — exactly as a third kind would
be. Nothing in the core imports this package; it is
re-exported from `score.itf.core.octo` so the two shipped kinds are there by default.
"""

from __future__ import annotations

from typing import Iterable

from ..model import claims as _claims
from ..planner.resolve import Octo
from . import capability, state
from .capability import (
    CAPABILITY,
    BindingClaim,
    CapabilityContractClaim,
    NodeClaim,
    PlannedNode,
    ProviderClaim,
    ShapeExpectationClaim,
    TargetPlan,
)
from .state import (
    STATE,
    ActionPlan,
    AssumeClaim,
    GoalClaim,
    PlannedStep,
    RelationClaim,
    StateContractClaim,
)

KINDS = (CAPABILITY, STATE)
RELATIONS = (capability.RELATION, state.RELATION)
CLAIM_TYPES = capability.CLAIM_TYPES + state.CLAIM_TYPES


def standard(*extra_kinds, relations: Iterable = ()) -> Octo:
    """An Octo with the standard kinds first, then any extra kinds and their relations."""
    return Octo(KINDS + tuple(extra_kinds), RELATIONS + tuple(relations))


CODES = standard().codes


def resolve_target(claims, *, precedence=()):
    """Gate 1. `precedence` lists origins lowest first; an origin not listed ranks below all listed."""
    return standard().resolve(
        CAPABILITY,
        claims,
        precedence=precedence,
    )


def resolve_actions(
    claims,
    target: TargetPlan,
    *,
    precedence=(),
    observed_states=frozenset(),
    assumed_states=frozenset(),
):
    """Gate 2, against Gate 1's plan.

    State identity is "scope:token". A StateContractClaim with scope="" is a template, instantiated in
    each scope where a goal or a requires needs its token; a scoped claim for the same token in that
    scope overrides the template by precedence. Unqualified names in requires/invalidates mean the
    instance's own scope. `uses` binds by the Gate 1 slot rule inside the instance's scope. Steps whose
    impl and resolved `uses` are identical collapse into one step delivering every state involved.

    `observed_states` is evidence a probe confirmed; `assumed_states` is the caller's word, with no
    evidence behind it. Both suppress a state's producer the same way, but only `assumed_states` (and
    any `AssumeClaim` in `claims`) is reported back in `plan.assumed`.
    """
    return standard().resolve(
        STATE,
        claims,
        upstream=target,
        precedence=precedence,
        observed_states=observed_states,
        assumed_states=assumed_states,
    )


def resolve(setup, init, **kw):
    """Both gates in sequence; the second is None when the first fails."""
    gate1 = {k: v for k, v in kw.items() if k in ("precedence",)}
    target_res = resolve_target(setup, **gate1)
    if not target_res.ok():
        return target_res, None
    gate2 = {k: v for k, v in kw.items() if k in ("precedence", "observed_states", "assumed_states")}
    return target_res, resolve_actions(init, target_res.plan, **gate2)


def claim_from_json(data: dict, types=CLAIM_TYPES):
    return _claims.claim_from_json(data, types)


def claims_from_json(data, types=CLAIM_TYPES) -> frozenset:
    return _claims.claims_from_json(data, types)
