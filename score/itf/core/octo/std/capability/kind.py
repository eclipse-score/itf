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
"""Gate 1 registered as a kind: its claim types, codes and relation to the next gate."""

from __future__ import annotations


from ...model.kinds import Kind
from ...model.relations import Relation
from .claims import BindingClaim, CapabilityContractClaim, NodeClaim, ProviderClaim, ShapeExpectationClaim
from .resolve import resolve_contract_to_node


# ---------------------------------------------------------------- registration

CLAIM_TYPES = (CapabilityContractClaim, ProviderClaim, NodeClaim, BindingClaim, ShapeExpectationClaim)

CODES = frozenset(
    {
        "CONTRACT_CONFLICT",
        "PROVIDER_CONFLICT",
        "NAME_COLLISION",
        "ALIAS_UNRESOLVED",
        "ALIAS_CYCLE",
        "REBIND_ORPHAN",
        "PROVIDER_UNKNOWN",
        "PROVIDER_CONTRACT_MISMATCH",
        "NO_PROVIDER",
        "PROVIDER_AMBIGUOUS",
        "BINDING_UNKNOWN",
        "BINDING_CONTRACT_MISMATCH",
        "SLOT_AMBIGUOUS",
        "SLOT_UNSATISFIED",
        "CYCLE",
    }
)

CAPABILITY = Kind(
    name="capability",
    ref="contract-to-node",
    roles=frozenset({"needs"}),
    idempotent=True,
    permanent=True,
    reversible=False,
    realization="construct",
    evidence="shape",
    scoped=True,
    identity="scope-name",
)

RELATION = Relation(
    ref="contract-to-node",
    claim_types=CLAIM_TYPES,
    resolve=resolve_contract_to_node,
    codes=CODES,
)
