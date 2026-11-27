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
"""Gate 2's output: the action plan and its planned steps."""

from __future__ import annotations

from dataclasses import dataclass


from ...model.claims import Pairs
from ...model.plans import Edge


# ---------------------------------------------------------------- action plan (Gate 2 output)


@dataclass(frozen=True)
class PlannedStep:
    key: str  # first of `delivers`; identifies the step
    impl: str
    probe: str  # "" = unprobed
    delivers: tuple[str, ...]  # "scope:token", sorted; >1 when also_delivers or collapsed
    requires: tuple[str, ...]  # "scope:token", sorted
    invalidates: tuple[str, ...]  # "scope:token", sorted
    uses: Pairs  # ((slot, node ref), ...) — refs into the TargetPlan
    # ((state id, probe ref), ...) for each delivered state that has its own evidence; a collapsed
    # step keeps every contract's probe. Empty in plans written before per-state probes: then
    # `probe` vouches for every delivered state.
    probes: Pairs = ()

    def state_probes(self) -> Pairs:
        """((state id, probe ref), ...): which probe is evidence for which delivered state."""
        if self.probes:
            return self.probes
        return tuple((d, self.probe) for d in self.delivers) if self.probe else ()


@dataclass(frozen=True)
class ActionPlan:
    goals: tuple[str, ...]  # "scope:token", sorted
    observed_at_plan_time: tuple[str, ...]
    steps: tuple[PlannedStep, ...]  # in execution order
    edges: tuple[Edge, ...]
    unprobed: tuple[str, ...]  # step keys with probe == ""
    assumed: tuple[str, ...] = ()  # "scope:token", sorted — producer suppressed, no evidence
    kinds: tuple[str, ...] = ()  # the kind set this plan was resolved under

    def to_json(self) -> dict:
        return {
            "goals": list(self.goals),
            "observed_at_plan_time": list(self.observed_at_plan_time),
            "assumed": list(self.assumed),
            "steps": [
                {
                    "key": s.key,
                    "impl": s.impl,
                    "probe": s.probe,
                    "probes": {k: v for k, v in s.probes},
                    "delivers": list(s.delivers),
                    "requires": list(s.requires),
                    "invalidates": list(s.invalidates),
                    "uses": {k: v for k, v in s.uses},
                }
                for s in self.steps
            ],
            "edges": [{"before": e.before, "after": e.after, "reason": e.reason, "state": e.state} for e in self.edges],
            "unprobed": list(self.unprobed),
            "kinds": list(self.kinds),
        }

    @classmethod
    def from_json(cls, data: dict) -> "ActionPlan":
        steps = tuple(
            PlannedStep(
                key=s["key"],
                impl=s["impl"],
                probe=s["probe"],
                delivers=tuple(s["delivers"]),
                requires=tuple(s["requires"]),
                invalidates=tuple(s["invalidates"]),
                uses=tuple(sorted(s["uses"].items())),
                probes=tuple(sorted(s.get("probes", {}).items())),
            )
            for s in data["steps"]
        )
        edges = tuple(
            Edge(before=e["before"], after=e["after"], reason=e["reason"], state=e["state"]) for e in data["edges"]
        )
        return cls(
            goals=tuple(data["goals"]),
            observed_at_plan_time=tuple(data["observed_at_plan_time"]),
            steps=steps,
            edges=edges,
            unprobed=tuple(data["unprobed"]),
            assumed=tuple(data.get("assumed", ())),
            kinds=tuple(data.get("kinds", ())),
        )
