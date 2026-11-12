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
"""Gate 1 tests: which factory fills which role, and how.

Non-domain reference vocabulary: a web shop. Contracts: db.pool, itf.capabilities.descriptor.endpoint,
cache.client, http.api, db.credentials.
"""

from __future__ import annotations

import ast
import json
import random
import sys
from pathlib import Path

import pytest

from score.itf.core.octo import (
    CAPABILITY,
    CapabilityContractClaim,
    Kind,
    Member,
    Need,
    NodeClaim,
    BindingClaim,
    ProviderClaim,
    Shape,
    resolve_target,
)
from score.itf.core.octo.std import capability as capabilities


def _endpoint_contracts():
    return {
        CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint", gives=Shape.of("host", "port")),
    }


def test_A_1_1_an_unfilled_slot_is_unsatisfied_even_when_one_factory_could_fill_it():
    """No role is created behind the author's back: the target file says what exists."""
    contracts = frozenset(_endpoint_contracts() | {CapabilityContractClaim(token="db.pool")})
    providers = frozenset(
        {
            ProviderClaim(
                name="acme.endpoint",
                implements="itf.capabilities.descriptor.endpoint",
                gives=Shape.of("host", "port"),
                impl="m:endpoint",
            ),
            ProviderClaim(
                name="acme.pool",
                implements="db.pool",
                impl="m:pool",
                needs=(Need(slot="endpoint", contract="itf.capabilities.descriptor.endpoint"),),
            ),
        }
    )
    nodes = frozenset({NodeClaim(scope="shop", name="pool", contract="db.pool", using="acme.pool")})
    res = resolve_target(contracts | providers | nodes)
    assert res.plan is None
    assert [(d.code, d.subject) for d in res.diagnostics] == [("SLOT_UNSATISFIED", "shop.pool#endpoint")]


def test_A_1_2_two_names_one_contract_two_nodes():
    contracts = frozenset({CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint")})
    providers = frozenset(
        {
            ProviderClaim(name="acme.endpoint", implements="itf.capabilities.descriptor.endpoint", impl="m:endpoint"),
        }
    )
    nodes = frozenset(
        {
            NodeClaim(
                scope="shop", name="primary", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint"
            ),
            NodeClaim(
                scope="shop", name="secondary", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint"
            ),
        }
    )
    res = resolve_target(contracts | providers | nodes)
    assert res.ok(), res.diagnostics
    assert len(res.plan.nodes) == 2
    assert {n.name for n in res.plan.nodes} == {"primary", "secondary"}


def test_A_1_3_higher_origin_overrides_no_consumer_change():
    contracts = frozenset({CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint")})
    providers = frozenset(
        {
            ProviderClaim(name="acme.endpoint.v1", implements="itf.capabilities.descriptor.endpoint", impl="m:v1"),
            ProviderClaim(name="acme.endpoint.v2", implements="itf.capabilities.descriptor.endpoint", impl="m:v2"),
        }
    )
    low = NodeClaim(
        scope="shop",
        name="ep",
        contract="itf.capabilities.descriptor.endpoint",
        using="acme.endpoint.v1",
        origin="pack",
    )
    high = NodeClaim(
        scope="shop",
        name="ep",
        contract="itf.capabilities.descriptor.endpoint",
        using="acme.endpoint.v2",
        origin="policy",
    )
    res = resolve_target(contracts | providers | frozenset({low, high}), precedence=("pack", "policy"))
    assert res.ok(), res.diagnostics
    assert res.plan.node("shop.ep").provider == "acme.endpoint.v2"


def test_A_1_4_sole_candidate_binds():
    contracts = frozenset(_endpoint_contracts() | {CapabilityContractClaim(token="db.pool")})
    providers = frozenset(
        {
            ProviderClaim(name="acme.endpoint", implements="itf.capabilities.descriptor.endpoint", impl="m:endpoint"),
            ProviderClaim(
                name="acme.pool",
                implements="db.pool",
                impl="m:pool",
                needs=(
                    Need(
                        slot="endpoint",
                        contract="itf.capabilities.descriptor.endpoint",
                        expected=Shape.of("host"),
                    ),
                ),
            ),
        }
    )
    nodes = frozenset(
        {
            NodeClaim(scope="shop", name="ep", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint"),
            NodeClaim(scope="shop", name="pool", contract="db.pool", using="acme.pool"),
        }
    )
    res = resolve_target(contracts | providers | nodes)
    assert res.ok(), res.diagnostics
    pool = res.plan.node("shop.pool")
    assert dict(pool.bindings)["endpoint"] == "shop.ep"
    assert dict(pool.why_bindings)["endpoint"] == "sole-candidate-in-scope"
    assert len([n for n in res.plan.nodes if n.contract == "itf.capabilities.descriptor.endpoint"]) == 1


def test_A_1_5_slot_ambiguous_names_both_candidates():
    contracts = frozenset(_endpoint_contracts() | {CapabilityContractClaim(token="db.pool")})
    providers = frozenset(
        {
            ProviderClaim(name="acme.endpoint", implements="itf.capabilities.descriptor.endpoint", impl="m:endpoint"),
            ProviderClaim(
                name="acme.pool",
                implements="db.pool",
                impl="m:pool",
                needs=(Need(slot="endpoint", contract="itf.capabilities.descriptor.endpoint"),),
            ),
        }
    )
    nodes = frozenset(
        {
            NodeClaim(scope="shop", name="ep1", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint"),
            NodeClaim(scope="shop", name="ep2", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint"),
            NodeClaim(scope="shop", name="pool", contract="db.pool", using="acme.pool"),
        }
    )
    res = resolve_target(contracts | providers | nodes)
    assert not res.ok()
    d = [x for x in res.diagnostics if x.code == "SLOT_AMBIGUOUS"]
    assert len(d) == 1
    assert d[0].subject == "shop.pool#endpoint"
    candidates = {v for k, v in d[0].evidence}
    assert candidates == {"shop.ep1", "shop.ep2"}


def test_A_1_6_shape_per_seam_not_per_contract():
    contracts = frozenset(
        {
            CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint"),
            CapabilityContractClaim(token="cache.client"),
            CapabilityContractClaim(token="db.pool"),
        }
    )
    providers = frozenset(
        {
            ProviderClaim(
                name="acme.endpoint",
                implements="itf.capabilities.descriptor.endpoint",
                gives=Shape.of("host"),
                impl="m:endpoint",
            ),
            ProviderClaim(
                name="acme.cache",
                implements="cache.client",
                impl="m:cache",
                needs=(
                    Need(
                        slot="endpoint",
                        contract="itf.capabilities.descriptor.endpoint",
                        expected=Shape.of("host", "port"),
                    ),
                ),
            ),
            ProviderClaim(
                name="acme.pool",
                implements="db.pool",
                impl="m:pool",
                needs=(
                    Need(slot="endpoint", contract="itf.capabilities.descriptor.endpoint", expected=Shape.of("host")),
                ),
            ),
        }
    )
    nodes = frozenset(
        {
            NodeClaim(scope="shop", name="ep", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint"),
            NodeClaim(scope="shop", name="cache", contract="cache.client", using="acme.cache"),
            NodeClaim(scope="shop", name="pool", contract="db.pool", using="acme.pool"),
        }
    )
    res = resolve_target(contracts | providers | nodes)
    assert not res.ok()
    codes = {d.code for d in res.diagnostics}
    assert codes == {"SHAPE_MISSING_MEMBER"}
    subjects = {d.subject for d in res.diagnostics}
    assert subjects == {"shop.cache#endpoint"}


def test_A_1_7_consumer_contract_expectation_unioned():
    contracts = frozenset(
        {
            CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint"),
            CapabilityContractClaim(
                token="cache.client",
                needs=(
                    Need(slot="endpoint", contract="itf.capabilities.descriptor.endpoint", expected=Shape.of("port")),
                ),
            ),
        }
    )
    providers = frozenset(
        {
            ProviderClaim(
                name="acme.endpoint",
                implements="itf.capabilities.descriptor.endpoint",
                gives=Shape.of("host"),
                impl="m:endpoint",
            ),
            ProviderClaim(
                name="acme.cache",
                implements="cache.client",
                impl="m:cache",
                needs=(Need(slot="endpoint", contract="itf.capabilities.descriptor.endpoint"),),
            ),
        }
    )
    nodes = frozenset(
        {
            NodeClaim(scope="shop", name="ep", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint"),
            NodeClaim(scope="shop", name="cache", contract="cache.client", using="acme.cache"),
        }
    )
    res = resolve_target(contracts | providers | nodes)
    assert not res.ok()
    d = [x for x in res.diagnostics if x.code == "SHAPE_MISSING_MEMBER"]
    assert len(d) == 1
    assert dict(d[0].evidence).get("member") == "port"


def test_A_1_8_alias_is_second_name_not_second_node():
    contracts = frozenset({CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint")})
    providers = frozenset(
        {ProviderClaim(name="acme.endpoint", implements="itf.capabilities.descriptor.endpoint", impl="m:endpoint")}
    )
    nodes = frozenset(
        {
            NodeClaim(scope="shop", name="ep", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint"),
            NodeClaim(scope="warehouse", name="ep", alias="shop.ep"),
        }
    )
    res = resolve_target(contracts | providers | nodes)
    assert res.ok(), res.diagnostics
    assert len(res.plan.nodes) == 1
    assert res.plan.resolve("warehouse.ep") == "shop.ep"


def _golden_claim_set():
    contracts = frozenset(
        {
            CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint", gives=Shape.of("host", "port")),
            CapabilityContractClaim(token="db.credentials", gives=Shape.of("user")),
            CapabilityContractClaim(token="db.pool"),
        }
    )
    providers = frozenset(
        {
            ProviderClaim(
                name="acme.endpoint",
                implements="itf.capabilities.descriptor.endpoint",
                gives=Shape.of("host", "port"),
                impl="m:endpoint",
            ),
            ProviderClaim(name="acme.credentials", implements="db.credentials", impl="m:creds"),
            ProviderClaim(
                name="acme.pool",
                implements="db.pool",
                impl="m:pool",
                needs=(
                    Need(
                        slot="endpoint",
                        contract="itf.capabilities.descriptor.endpoint",
                        expected=Shape.of("host", "port"),
                    ),
                    Need(slot="credentials", contract="db.credentials", expected=Shape.of("user")),
                ),
            ),
        }
    )
    nodes = frozenset(
        {
            NodeClaim(scope="shop", name="ep", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint"),
            NodeClaim(scope="shop", name="credentials", contract="db.credentials", using="acme.credentials"),
            NodeClaim(scope="shop", name="pool", contract="db.pool", using="acme.pool"),
        }
    )
    return contracts | providers | nodes


def test_A_1_9_two_hundred_shuffles_one_canonical_plan():
    claims = list(_golden_claim_set())
    canonical = None
    for _ in range(200):
        random.shuffle(claims)
        res = resolve_target(frozenset(claims))
        assert res.ok(), res.diagnostics
        blob = json.dumps(res.plan.to_json(), sort_keys=True)
        if canonical is None:
            canonical = blob
        else:
            assert blob == canonical


def test_A_1_10_cycle_reported_rotation_normalised():
    contracts = frozenset(
        {
            CapabilityContractClaim(token="a.contract"),
            CapabilityContractClaim(token="b.contract"),
        }
    )
    providers = frozenset(
        {
            ProviderClaim(
                name="p.a", implements="a.contract", impl="m:a", needs=(Need(slot="b", contract="b.contract"),)
            ),
            ProviderClaim(
                name="p.b", implements="b.contract", impl="m:b", needs=(Need(slot="a", contract="a.contract"),)
            ),
        }
    )
    nodes = frozenset(
        {
            NodeClaim(scope="shop", name="a", contract="a.contract", using="p.a", bind=(("b", "shop.b"),)),
            NodeClaim(scope="shop", name="b", contract="b.contract", using="p.b", bind=(("a", "shop.a"),)),
        }
    )
    res = resolve_target(contracts | providers | nodes)
    assert not res.ok()
    d = [x for x in res.diagnostics if x.code == "CYCLE"]
    assert len(d) == 1
    assert d[0].subject == "shop.a"


def test_A_1_11_no_branch_on_kind_name():
    files = sorted(Path(capabilities.__file__).parent.glob("*.py"))  # the kind is a package of modules
    assert len(files) > 1
    for node in (n for f in files for n in ast.walk(ast.parse(f.read_text()))):
        if isinstance(node, (ast.If,)):
            test_src = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
            assert "capability" not in test_src.lower()
            assert '"state"' not in test_src.lower() and "'state'" not in test_src.lower()


def test_A_1_11_descriptor_change_changes_behaviour():
    contracts = frozenset({CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint")})
    providers = frozenset(
        {
            ProviderClaim(name="acme.endpoint.1", implements="itf.capabilities.descriptor.endpoint", impl="m:1"),
            ProviderClaim(name="acme.endpoint.2", implements="itf.capabilities.descriptor.endpoint", impl="m:2"),
        }
    )
    scoped_nodes = frozenset(
        {
            NodeClaim(
                scope="shop", name="ep", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint.1"
            ),
            NodeClaim(
                scope="warehouse", name="ep", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint.2"
            ),
        }
    )
    scoped_kind = Kind(
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
    unscoped_kind = dataclasses_replace_scoped(scoped_kind, scoped=False)

    plan_scoped, diags_scoped = capabilities.resolve_contract_to_node(scoped_kind, contracts | providers | scoped_nodes)
    assert not diags_scoped
    assert len(plan_scoped.nodes) == 2

    plan_unscoped, diags_unscoped = capabilities.resolve_contract_to_node(
        unscoped_kind, contracts | providers | scoped_nodes
    )
    # scoped=False collapses both nodes onto one identity; since they disagree (different
    # `using`), that now surfaces as a NAME_COLLISION -- the descriptor field alone changed
    # the observed behaviour, with no change to the resolver.
    assert diags_unscoped and diags_unscoped[0].code == "NAME_COLLISION"


def dataclasses_replace_scoped(kind, **kw):
    import dataclasses

    return dataclasses.replace(kind, **kw)


def test_A_1_12_rebind_changes_one_slot_only():
    contracts = frozenset(_endpoint_contracts() | {CapabilityContractClaim(token="db.pool")})
    providers = frozenset(
        {
            ProviderClaim(name="acme.endpoint", implements="itf.capabilities.descriptor.endpoint", impl="m:endpoint"),
            ProviderClaim(
                name="acme.pool",
                implements="db.pool",
                impl="m:pool",
                needs=(
                    Need(
                        slot="endpoint",
                        contract="itf.capabilities.descriptor.endpoint",
                        expected=Shape.of("host"),
                    ),
                ),
            ),
        }
    )
    nodes = frozenset(
        {
            NodeClaim(scope="shop", name="ep1", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint"),
            NodeClaim(scope="shop", name="ep2", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint"),
            NodeClaim(
                scope="shop", name="pool", contract="db.pool", using="acme.pool", bind=(("endpoint", "shop.ep1"),)
            ),
        }
    )
    rebind = BindingClaim(scope="shop", name="pool", bind=(("endpoint", "shop.ep2"),), origin="policy")
    res = resolve_target(contracts | providers | nodes | frozenset({rebind}), precedence=("pack", "policy"))
    assert res.ok(), res.diagnostics
    pool = res.plan.node("shop.pool")
    assert dict(pool.bindings)["endpoint"] == "shop.ep2"
    assert dict(pool.why_bindings)["endpoint"] == "rebind"
    assert pool.provider == "acme.pool"


def test_no_provider_and_provider_ambiguous():
    contracts = frozenset({CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint")})
    nodes = frozenset({NodeClaim(scope="shop", name="ep", contract="itf.capabilities.descriptor.endpoint")})
    res = resolve_target(contracts | nodes)
    assert not res.ok()
    assert res.diagnostics[0].code == "NO_PROVIDER"

    providers = frozenset(
        {
            ProviderClaim(name="a", implements="itf.capabilities.descriptor.endpoint", impl="m:a"),
            ProviderClaim(name="b", implements="itf.capabilities.descriptor.endpoint", impl="m:b"),
        }
    )
    res2 = resolve_target(contracts | providers | nodes)
    assert not res2.ok()
    assert res2.diagnostics[0].code == "PROVIDER_AMBIGUOUS"


def test_binding_unknown_and_contract_mismatch():
    contracts = frozenset(
        {
            CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint"),
            CapabilityContractClaim(token="cache.client"),
            CapabilityContractClaim(token="db.pool"),
        }
    )
    providers = frozenset(
        {
            ProviderClaim(name="acme.endpoint", implements="itf.capabilities.descriptor.endpoint", impl="m:endpoint"),
            ProviderClaim(name="acme.cache", implements="cache.client", impl="m:cache"),
            ProviderClaim(
                name="acme.pool",
                implements="db.pool",
                impl="m:pool",
                needs=(Need(slot="endpoint", contract="itf.capabilities.descriptor.endpoint"),),
            ),
        }
    )
    nodes_unknown = frozenset(
        {
            NodeClaim(
                scope="shop", name="pool", contract="db.pool", using="acme.pool", bind=(("endpoint", "shop.missing"),)
            ),
        }
    )
    res = resolve_target(contracts | providers | nodes_unknown)
    assert not res.ok()
    assert res.diagnostics[0].code == "BINDING_UNKNOWN"

    nodes_mismatch = frozenset(
        {
            NodeClaim(scope="shop", name="cache", contract="cache.client", using="acme.cache"),
            NodeClaim(
                scope="shop", name="pool", contract="db.pool", using="acme.pool", bind=(("endpoint", "shop.cache"),)
            ),
        }
    )
    res2 = resolve_target(contracts | providers | nodes_mismatch)
    assert not res2.ok()
    assert res2.diagnostics[0].code == "BINDING_CONTRACT_MISMATCH"


def test_provider_unknown_and_contract_mismatch():
    contracts = frozenset(
        {
            CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint"),
            CapabilityContractClaim(token="cache.client"),
        }
    )
    providers = frozenset({ProviderClaim(name="acme.cache", implements="cache.client", impl="m:cache")})
    nodes = frozenset(
        {NodeClaim(scope="shop", name="ep", contract="itf.capabilities.descriptor.endpoint", using="acme.missing")}
    )
    res = resolve_target(contracts | providers | nodes)
    assert not res.ok()
    assert res.diagnostics[0].code == "PROVIDER_UNKNOWN"

    nodes2 = frozenset(
        {NodeClaim(scope="shop", name="ep", contract="itf.capabilities.descriptor.endpoint", using="acme.cache")}
    )
    res2 = resolve_target(contracts | providers | nodes2)
    assert not res2.ok()
    assert res2.diagnostics[0].code == "PROVIDER_CONTRACT_MISMATCH"


def test_alias_unresolved_and_cycle():
    res = resolve_target(frozenset({NodeClaim(scope="shop", name="ep", alias="shop.missing")}))
    assert not res.ok()
    assert res.diagnostics[0].code == "ALIAS_UNRESOLVED"

    res2 = resolve_target(
        frozenset(
            {
                NodeClaim(scope="shop", name="a", alias="shop.b"),
                NodeClaim(scope="shop", name="b", alias="shop.a"),
            }
        )
    )
    assert not res2.ok()
    assert any(d.code == "ALIAS_CYCLE" for d in res2.diagnostics)


def test_name_collision_and_contract_conflict():
    a = NodeClaim(scope="shop", name="ep", contract="itf.capabilities.descriptor.endpoint", origin="pack1")
    b = NodeClaim(scope="shop", name="ep", contract="cache.client", origin="pack2")
    res = resolve_target(
        frozenset(
            {
                CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint"),
                CapabilityContractClaim(token="cache.client"),
                a,
                b,
            }
        ),
        precedence=("pack1", "pack2"),
    )
    # equal precedence (both unlisted vs listed at same implied rank isn't equal here);
    # force equal rank explicitly:
    res_equal = resolve_target(
        frozenset(
            {
                CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint"),
                CapabilityContractClaim(token="cache.client"),
                NodeClaim(scope="shop", name="ep", contract="itf.capabilities.descriptor.endpoint", origin="same"),
                NodeClaim(scope="shop", name="ep", contract="cache.client", origin="same"),
            }
        )
    )
    assert not res_equal.ok()
    assert any(d.code == "NAME_COLLISION" for d in res_equal.diagnostics)

    c1 = CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint", gives=Shape.of("host"))
    c2 = CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint", gives=Shape.of("port"))
    res_conflict = resolve_target(frozenset({c1, c2}))
    assert not res_conflict.ok()
    assert res_conflict.diagnostics[0].code == "CONTRACT_CONFLICT"


def test_rebind_orphan():
    orphan = BindingClaim(scope="shop", name="missing", bind=(("endpoint", "shop.ep"),))
    res = resolve_target(frozenset({orphan}))
    assert not res.ok()
    assert res.diagnostics[0].code == "REBIND_ORPHAN"


def test_claim_wrong_gate():
    from score.itf.core.octo import StateContractClaim

    res = resolve_target(frozenset({StateContractClaim(token="db_up")}))
    assert not res.ok()
    assert res.diagnostics[0].code == "CLAIM_WRONG_GATE"
    assert res.diagnostics[0].gate == 1
