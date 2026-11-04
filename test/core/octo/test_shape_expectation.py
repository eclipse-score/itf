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
"""`ShapeExpectationClaim` / `ctx.expect()`: a shape every node offering a contract must satisfy,
regardless of which consumer's `needs=`/`uses=` asked for it — additive across every claim for the
same contract, never a conflict.

Non-domain reference vocabulary: a web shop, matching `test_capabilities.py`.
"""

from __future__ import annotations

from score.itf.core.octo import (
    CapabilityContractClaim,
    Need,
    NodeClaim,
    ProviderClaim,
    Shape,
    ShapeExpectationClaim,
    resolve_target,
)


def _pool_consuming_an_endpoint(endpoint_shape: Shape = Shape()) -> tuple[frozenset, frozenset]:
    contracts = frozenset({CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint")})
    nodes = frozenset(
        {
            NodeClaim(
                scope="shop", name="endpoint", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint"
            ),
            NodeClaim(scope="shop", name="pool", contract="db.pool", using="acme.pool"),
        }
    )
    provider_pool = ProviderClaim(
        name="acme.pool",
        implements="db.pool",
        impl="m:pool",
        needs=(Need(slot="endpoint", contract="itf.capabilities.descriptor.endpoint", expected=endpoint_shape),),
    )
    return contracts, nodes, provider_pool


def test_a_consumer_that_expects_nothing_of_what_it_binds_to_is_an_error():
    contracts, nodes, provider_pool = _pool_consuming_an_endpoint()
    providers = frozenset(
        {
            ProviderClaim(
                name="acme.endpoint",
                implements="itf.capabilities.descriptor.endpoint",
                gives=Shape.of("host"),
                impl="m:endpoint",
            ),
            provider_pool,
        }
    )
    res = resolve_target(contracts | providers | nodes)
    assert [(d.code, d.subject) for d in res.diagnostics] == [("SHAPE_UNDECLARED", "shop.pool#endpoint")]


def test_shape_expectation_catches_a_provider_missing_the_member_no_consumer_asked_for():
    """The acceptance case: a policy requires more of a contract than any one consumer declared."""
    contracts, nodes, provider_pool = _pool_consuming_an_endpoint(endpoint_shape=Shape.of("host"))
    providers = frozenset(
        {
            ProviderClaim(
                name="acme.endpoint",
                implements="itf.capabilities.descriptor.endpoint",
                gives=Shape.of("host"),
                impl="m:endpoint",
            ),
            provider_pool,
        }
    )
    # without the expectation, "host" alone already satisfies the consumer's own need
    assert resolve_target(contracts | providers | nodes).ok()

    expectation = frozenset(
        {ShapeExpectationClaim(contract="itf.capabilities.descriptor.endpoint", shape=Shape.of("port"))}
    )
    res = resolve_target(contracts | providers | nodes | expectation)
    assert not res.ok()
    assert any(d.code == "SHAPE_MISSING_MEMBER" for d in res.diagnostics)


def test_shape_expectations_from_different_origins_union_rather_than_conflict():
    contracts, nodes, provider_pool = _pool_consuming_an_endpoint()
    providers = frozenset(
        {
            ProviderClaim(
                name="acme.endpoint",
                implements="itf.capabilities.descriptor.endpoint",
                gives=Shape.of("host", "port"),
                impl="m:endpoint",
            ),
            provider_pool,
        }
    )
    expectations = frozenset(
        {
            ShapeExpectationClaim(
                contract="itf.capabilities.descriptor.endpoint", shape=Shape.of("host"), origin="pack_a"
            ),
            ShapeExpectationClaim(
                contract="itf.capabilities.descriptor.endpoint", shape=Shape.of("port"), origin="pack_b"
            ),
        }
    )
    # the provider gives both; the union of two partial expectations is satisfied, not a conflict
    res = resolve_target(contracts | providers | nodes | expectations)
    assert res.ok(), res.diagnostics


def test_the_union_is_enforced_not_just_the_last_claim_considered():
    contracts, nodes, provider_pool = _pool_consuming_an_endpoint()
    providers_missing_port = frozenset(
        {
            ProviderClaim(
                name="acme.endpoint",
                implements="itf.capabilities.descriptor.endpoint",
                gives=Shape.of("host"),
                impl="m:endpoint",
            ),
            provider_pool,
        }
    )
    expectations = frozenset(
        {
            ShapeExpectationClaim(
                contract="itf.capabilities.descriptor.endpoint", shape=Shape.of("host"), origin="pack_a"
            ),
            ShapeExpectationClaim(
                contract="itf.capabilities.descriptor.endpoint", shape=Shape.of("port"), origin="pack_b"
            ),
        }
    )
    res = resolve_target(contracts | providers_missing_port | nodes | expectations)
    assert not res.ok()
    assert any(d.code == "SHAPE_MISSING_MEMBER" for d in res.diagnostics)


def test_a_declared_node_nothing_binds_is_still_held_to_the_expectation():
    """Only what someone expects is checked: an unbound node with no expectation passes."""
    provider = ProviderClaim(
        name="acme.endpoint", implements="itf.capabilities.descriptor.endpoint", gives=Shape.of("host"), impl="m:e"
    )
    node = NodeClaim(scope="shop", name="ep", contract="itf.capabilities.descriptor.endpoint")
    assert resolve_target({provider, node}).ok()

    res = resolve_target(
        {provider, node, ShapeExpectationClaim(contract="itf.capabilities.descriptor.endpoint", shape=Shape.of("port"))}
    )
    assert [(d.code, d.subject, d.evidence) for d in res.diagnostics] == [
        ("SHAPE_MISSING_MEMBER", "shop.ep", (("member", "port"),)),
    ]
