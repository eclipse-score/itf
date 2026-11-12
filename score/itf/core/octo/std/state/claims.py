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
"""Gate 2's input: the init claims (state contracts, goals, relations, assumptions)."""

from __future__ import annotations

from dataclasses import dataclass


from ...model.claims import Pairs
from ...model.shapes import Need


# ---------------------------------------------------------------- init claims (Gate 2)


@dataclass(frozen=True)
class StateContractClaim:
    token: str  # the state this delivers
    impl: str = ""
    probe: str = ""  # "" = unprobed
    requires: frozenset[str] = frozenset()  # "token" (same scope) or "scope:token"
    invalidates: frozenset[str] = frozenset()  # same form
    also_delivers: frozenset[str] = frozenset()
    uses: tuple[Need, ...] = ()
    bind: Pairs = ()  # ((slot, role name in the scope), ...): the explicit choice for a slot of `uses`
    scope: str = ""  # "" = published template, instantiated per scope that needs it
    origin: str = ""

    def subject(self) -> str:
        return f"state:{self.token}"

    def to_json(self) -> dict:
        return {
            "token": self.token,
            "impl": self.impl,
            "probe": self.probe,
            "requires": sorted(self.requires),
            "invalidates": sorted(self.invalidates),
            "also_delivers": sorted(self.also_delivers),
            "uses": [n.to_json() for n in self.uses],
            "bind": dict(self.bind),
            "scope": self.scope,
            "origin": self.origin,
        }

    @classmethod
    def from_json(cls, data: dict) -> "StateContractClaim":
        return cls(
            token=data["token"],
            impl=data.get("impl", ""),
            probe=data.get("probe", ""),
            requires=frozenset(data.get("requires", ())),
            invalidates=frozenset(data.get("invalidates", ())),
            also_delivers=frozenset(data.get("also_delivers", ())),
            uses=tuple(Need.from_json(n) for n in data.get("uses", ())),
            bind=tuple(sorted(data.get("bind", {}).items())),
            scope=data.get("scope", ""),
            origin=data.get("origin", ""),
        )


@dataclass(frozen=True)
class GoalClaim:
    scope: str
    states: frozenset[str]
    origin: str = ""

    def subject(self) -> str:
        return f"{self.scope}:goal"

    def to_json(self) -> dict:
        return {"scope": self.scope, "states": sorted(self.states), "origin": self.origin}

    @classmethod
    def from_json(cls, data: dict) -> "GoalClaim":
        return cls(scope=data["scope"], states=frozenset(data.get("states", ())), origin=data.get("origin", ""))


@dataclass(frozen=True)
class RelationClaim:
    state: str  # token of the state contract amended
    adds_requires: frozenset[str] = frozenset()
    adds_invalidates: frozenset[str] = frozenset()
    scope: str = ""  # "" = every scope
    origin: str = ""

    def subject(self) -> str:
        return f"state:{self.state}"

    def to_json(self) -> dict:
        return {
            "state": self.state,
            "adds_requires": sorted(self.adds_requires),
            "adds_invalidates": sorted(self.adds_invalidates),
            "scope": self.scope,
            "origin": self.origin,
        }

    @classmethod
    def from_json(cls, data: dict) -> "RelationClaim":
        return cls(
            state=data["state"],
            adds_requires=frozenset(data.get("adds_requires", ())),
            adds_invalidates=frozenset(data.get("adds_invalidates", ())),
            scope=data.get("scope", ""),
            origin=data.get("origin", ""),
        )


@dataclass(frozen=True)
class AssumeClaim:
    """Treat `token` as already true in `scope` ("" = every scope) without running its producer.

    `owner` and `reason` are opaque payload, like `NodeClaim.config`: OCTO carries them
    through to the plan and never interprets them.
    """

    scope: str
    token: str
    owner: str = ""
    reason: str = ""
    origin: str = ""

    def to_json(self) -> dict:
        return {
            "scope": self.scope,
            "token": self.token,
            "owner": self.owner,
            "reason": self.reason,
            "origin": self.origin,
        }

    @classmethod
    def from_json(cls, data: dict) -> "AssumeClaim":
        return cls(
            scope=data["scope"],
            token=data["token"],
            owner=data.get("owner", ""),
            reason=data.get("reason", ""),
            origin=data.get("origin", ""),
        )
