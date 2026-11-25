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
"""OCTO — the planner. Declarations in, plans or diagnostics out. Standard library only.

The core is kind-agnostic machinery:

    kinds.py         Kind: a contract kind's semantics as data
    relations.py     Relation: the algorithm a kind's ref names — the extension point
    resolve.py       Octo(kinds, relations).resolve(kind, claims, upstream=...)
    claims.py        what every claim shares: payload types, canonical JSON envelope
    plans.py         what every plan shares: Seam, Edge, Resolution
    diagnostics.py   Diagnostic, the core codes, the shared shape check
    shapes.py        what an object offers vs what a consumer expects, compared as data
    graph.py         toposort, cycle detection, reachability
    precedence.py    "higher origin wins; equal origins disagreeing is an error"

The two standard kinds are registered through that same surface, in std/:

    std/capability.py   Gate 1 — what must exist: claims, TargetPlan, the contract-to-node relation
    std/state.py        Gate 2 — what must happen: claims, ActionPlan, the condition-to-producer relation

Nothing here imports, constructs, or runs anything a contributor wrote.
"""

from .model.claims import claim_to_json, claims_to_json, subject_of
from .model.diagnostics import CORE_CODES, Diagnostic, shape_mismatches
from .model.kinds import Kind
from .model.plans import Edge, Resolution, Seam
from .model.relations import Relation
from .planner.resolve import KindSetInvalid, Octo
from .model.shapes import Member, Need, Shape, shape_of
from .std import (
    CAPABILITY,
    CLAIM_TYPES,
    CODES,
    KINDS,
    RELATIONS,
    STATE,
    ActionPlan,
    AssumeClaim,
    BindingClaim,
    CapabilityContractClaim,
    GoalClaim,
    NodeClaim,
    PlannedNode,
    PlannedStep,
    ProviderClaim,
    RelationClaim,
    ShapeExpectationClaim,
    StateContractClaim,
    TargetPlan,
    claim_from_json,
    claims_from_json,
    resolve,
    resolve_actions,
    resolve_target,
    standard,
)

__all__ = [
    # core
    "Kind",
    "Relation",
    "Octo",
    "KindSetInvalid",
    "Resolution",
    "Seam",
    "Edge",
    "Diagnostic",
    "CORE_CODES",
    "shape_mismatches",
    "Member",
    "Need",
    "Shape",
    "shape_of",
    "claim_to_json",
    "claims_to_json",
    "subject_of",
    # standard kinds
    "CAPABILITY",
    "STATE",
    "KINDS",
    "RELATIONS",
    "CLAIM_TYPES",
    "CODES",
    "standard",
    "ActionPlan",
    "AssumeClaim",
    "BindingClaim",
    "CapabilityContractClaim",
    "GoalClaim",
    "NodeClaim",
    "PlannedNode",
    "PlannedStep",
    "ProviderClaim",
    "RelationClaim",
    "ShapeExpectationClaim",
    "StateContractClaim",
    "TargetPlan",
    "claim_from_json",
    "claims_from_json",
    "resolve",
    "resolve_actions",
    "resolve_target",
]
