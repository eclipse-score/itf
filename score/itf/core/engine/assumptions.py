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
"""The human-facing detail behind OCTO's bare `ActionPlan.assumed` ids: who asserted the state and
why, for `plan.json` and anyone reviewing a run. OCTO itself never sees `owner` or `reason`
as meaningful — it only carries them as opaque payload on `AssumeClaim`.
"""

from __future__ import annotations

from ..octo import AssumeClaim


def describe_assumed(
    action_plan, init_claims, *, request_ids=frozenset(), request_owner: str = "", request_reason: str = ""
) -> tuple[dict, ...]:
    policy: dict[tuple[str, str], AssumeClaim] = {}
    for c in init_claims:
        if isinstance(c, AssumeClaim):
            policy.setdefault((c.scope, c.token), c)

    out = []
    for state_id in action_plan.assumed:
        scope, token = state_id.split(":", 1)
        if state_id in request_ids:
            out.append(
                {
                    "state": state_id,
                    "owner": request_owner,
                    "reason": request_reason,
                    "origin": "request",
                }
            )
            continue
        claim = policy.get((scope, token)) or policy.get(("", token))
        out.append(
            {
                "state": state_id,
                "owner": claim.owner if claim else "",
                "reason": claim.reason if claim else "",
                "origin": claim.origin if claim else "",
            }
        )
    return tuple(out)
