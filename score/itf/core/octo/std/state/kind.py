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
"""Gate 2 registered as a kind: its claim types, codes and relation to the previous gate."""

from __future__ import annotations


from ...model.kinds import Kind
from ...model.relations import Relation
from .claims import AssumeClaim, GoalClaim, RelationClaim, StateContractClaim
from .resolve import resolve_condition_to_producer


# ---------------------------------------------------------------- registration

CLAIM_TYPES = (StateContractClaim, GoalClaim, RelationClaim, AssumeClaim)

CODES = frozenset(
    {
        "STATE_CONFLICT",
        "RELATION_ORPHAN",
        "USES_UNSATISFIED",
        "USES_AMBIGUOUS",
        "USES_BIND_INVALID",
        "STATE_UNREACHABLE",
        "STATE_CYCLE",
        "ORDER_AMBIGUOUS",
        "ASSUMPTION_CONFLICT",
    }
)

STATE = Kind(
    name="state",
    ref="condition-to-producer",
    roles=frozenset({"needs", "produces", "destroys", "uses"}),
    idempotent=False,
    permanent=False,
    reversible=True,
    realization="invoke",
    evidence="probe",
    scoped=True,
    identity="token",
)

RELATION = Relation(
    ref="condition-to-producer",
    claim_types=CLAIM_TYPES,
    resolve=resolve_condition_to_producer,
    codes=CODES,
    edge_reasons=frozenset({"delivers-requires", "invalidates"}),
    upstream="contract-to-node",
)
