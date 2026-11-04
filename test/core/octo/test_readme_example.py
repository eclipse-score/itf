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
"""Keep the standalone guide's first two-gate example executable."""

from score.itf.core.octo import (
    CapabilityContractClaim,
    GoalClaim,
    Need,
    NodeClaim,
    ProviderClaim,
    Shape,
    StateContractClaim,
    resolve_actions,
    resolve_target,
)


def test_first_plan_from_standalone_guide():
    setup = frozenset(
        {
            CapabilityContractClaim(token="itf.capabilities.descriptor.endpoint", gives=Shape.of("host", "port")),
            CapabilityContractClaim(token="db.pool"),
            ProviderClaim(
                name="acme.endpoint",
                implements="itf.capabilities.descriptor.endpoint",
                gives=Shape.of("host", "port"),
                impl="my_module:make_endpoint",
            ),
            ProviderClaim(
                name="acme.pool",
                implements="db.pool",
                impl="my_module:make_pool",
                needs=(
                    Need(
                        slot="endpoint",
                        contract="itf.capabilities.descriptor.endpoint",
                        expected=Shape.of("host", "port"),
                    ),
                ),
            ),
            NodeClaim(
                scope="shop", name="endpoint", contract="itf.capabilities.descriptor.endpoint", using="acme.endpoint"
            ),
            NodeClaim(scope="shop", name="pool", contract="db.pool", using="acme.pool"),
        }
    )
    target = resolve_target(setup)
    assert target.ok(), target.diagnostics
    assert dict(target.plan.node("shop.pool").bindings)["endpoint"] == "shop.endpoint"

    init = frozenset(
        {
            StateContractClaim(token="db_up", scope="shop", impl="my_module:start_db"),
            StateContractClaim(
                token="schema_migrated", scope="shop", impl="my_module:migrate", requires=frozenset({"db_up"})
            ),
            GoalClaim(scope="shop", states=frozenset({"schema_migrated"})),
        }
    )
    actions = resolve_actions(init, target.plan)
    assert actions.ok(), actions.diagnostics
    assert [step.key for step in actions.plan.steps] == ["shop:db_up", "shop:schema_migrated"]
