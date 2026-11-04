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
"""How a role is shown: `command (acme.exec)`, a state `platform.up by acme.start`."""

from __future__ import annotations


def node_label(name: str, factory: str | None = None) -> str:
    return name if not factory else f"{name} ({factory})"


def label_steps(action_json: dict | None, catalog) -> dict | None:
    """The action plan as JSON, each step with the label of the action that runs it (`"by": "acme.start"`),
    so a plan reads `platform.up by acme.start`."""
    if action_json is None or catalog is None:
        return action_json
    by_impl = {desc.impl: label for label, desc in catalog.action_descs.items()}
    steps = [{**s, "by": by_impl[s["impl"]]} if s.get("impl") in by_impl else s for s in action_json.get("steps", ())]
    return {**action_json, "steps": steps}
