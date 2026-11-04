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
"""Gate 1's input: the setup claims (contracts, providers, shape expectations, nodes, bindings)."""

from __future__ import annotations

from dataclasses import dataclass


from ...model.claims import Pairs
from ...model.shapes import Need, Shape


# ---------------------------------------------------------------- setup claims (Gate 1)


@dataclass(frozen=True)
class CapabilityContractClaim:
    token: str
    gives: Shape = Shape()
    needs: tuple[Need, ...] = ()
    origin: str = ""

    def subject(self) -> str:
        return f"contract:{self.token}"

    def to_json(self) -> dict:
        return {
            "token": self.token,
            "gives": self.gives.to_json(),
            "needs": [n.to_json() for n in self.needs],
            "origin": self.origin,
        }

    @classmethod
    def from_json(cls, data: dict) -> "CapabilityContractClaim":
        return cls(
            token=data["token"],
            gives=Shape.from_json(data.get("gives", {})),
            needs=tuple(Need.from_json(n) for n in data.get("needs", ())),
            origin=data.get("origin", ""),
        )


@dataclass(frozen=True)
class ProviderClaim:
    name: str
    implements: str
    gives: Shape = Shape()
    needs: tuple[Need, ...] = ()
    impl: str = ""  # "module:qualname", opaque to OCTO
    origin: str = ""

    def subject(self) -> str:
        return f"provider:{self.name}"

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "implements": self.implements,
            "gives": self.gives.to_json(),
            "needs": [n.to_json() for n in self.needs],
            "impl": self.impl,
            "origin": self.origin,
        }

    @classmethod
    def from_json(cls, data: dict) -> "ProviderClaim":
        return cls(
            name=data["name"],
            implements=data["implements"],
            gives=Shape.from_json(data.get("gives", {})),
            needs=tuple(Need.from_json(n) for n in data.get("needs", ())),
            impl=data.get("impl", ""),
            origin=data.get("origin", ""),
        )


@dataclass(frozen=True)
class ShapeExpectationClaim:
    """A shape every node offering `contract` must satisfy, regardless of which consumer's `needs`
    asked for it. Additive across every claim for the same contract: two contributors'
    expectations for the same contract union their members, they never conflict the way two
    `NodeClaim`s at equal origin would — the same "equal origins add up, never pick a winner"
    treatment `GoalClaim`/`RelationClaim` already get in Gate 2, applied to Gate 1's shape check.
    """

    contract: str
    shape: Shape = Shape()
    origin: str = ""

    def to_json(self) -> dict:
        return {"contract": self.contract, "shape": self.shape.to_json(), "origin": self.origin}

    @classmethod
    def from_json(cls, data: dict) -> "ShapeExpectationClaim":
        return cls(
            contract=data["contract"],
            shape=Shape.from_json(data.get("shape", {})),
            origin=data.get("origin", ""),
        )


@dataclass(frozen=True)
class NodeClaim:
    scope: str
    name: str
    contract: str | None = None  # None: taken from `using`'s provider, or alias set
    using: str | None = None  # provider name
    bind: Pairs = ()  # ((slot, "name" | "scope.name"), ...)
    config: Pairs = ()  # ((key, Scalar), ...)
    alias: str | None = None  # "scope.name"
    origin: str = ""

    def subject(self) -> str:
        return f"{self.scope}.{self.name}"

    def to_json(self) -> dict:
        return {
            "scope": self.scope,
            "name": self.name,
            "contract": self.contract,
            "using": self.using,
            "bind": dict(self.bind),
            "config": dict(self.config),
            "alias": self.alias,
            "origin": self.origin,
        }

    @classmethod
    def from_json(cls, data: dict) -> "NodeClaim":
        return cls(
            scope=data["scope"],
            name=data["name"],
            contract=data.get("contract"),
            using=data.get("using"),
            bind=tuple(sorted(data.get("bind", {}).items())),
            config=tuple(sorted(data.get("config", {}).items())),
            alias=data.get("alias"),
            origin=data.get("origin", ""),
        )


@dataclass(frozen=True)
class BindingClaim:
    scope: str
    name: str
    bind: Pairs  # ((slot, "name" | "scope.name"), ...)
    origin: str = ""

    def subject(self) -> str:
        return f"{self.scope}.{self.name}"

    def to_json(self) -> dict:
        return {"scope": self.scope, "name": self.name, "bind": dict(self.bind), "origin": self.origin}

    @classmethod
    def from_json(cls, data: dict) -> "BindingClaim":
        return cls(
            scope=data["scope"],
            name=data["name"],
            bind=tuple(sorted(data.get("bind", {}).items())),
            origin=data.get("origin", ""),
        )
