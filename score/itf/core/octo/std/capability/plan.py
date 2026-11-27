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
"""Gate 1's output: the target plan, its planned nodes and its lookups."""

from __future__ import annotations

from dataclasses import dataclass

import functools


from ...model.claims import Pairs
from ...model.plans import Seam
from ...model.shapes import Shape


# ---------------------------------------------------------------- target plan (Gate 1 output)


@dataclass(frozen=True)
class PlannedNode:
    scope: str
    name: str
    contract: str
    provider: str
    impl: str
    config: Pairs  # ((key, Scalar), ...)
    bindings: Pairs  # ((slot, "scope.name"), ...) — always resolved node refs
    why_provider: str  # explicit-using | sole-implementation
    why_bindings: Pairs  # ((slot, explicit|rebind|sole-candidate-in-scope|alias), ...)
    gives: Shape = Shape()  # what the node offers: its provider's gives ∪ its contract's

    @property
    def ref(self) -> str:
        return f"{self.scope}.{self.name}"


@dataclass(frozen=True)
class TargetPlan:
    nodes: tuple[PlannedNode, ...]  # sorted by ref
    construction_order: tuple[str, ...]  # node refs
    aliases: Pairs  # (("scope.alias", "scope.node"), ...)
    seams: tuple[Seam, ...]
    kinds: tuple[str, ...] = ()  # the kind set this plan was resolved under

    def resolve(self, ref: str) -> str:
        """Follow aliases: "gw.capture" -> "shop.capture". Unknown ref -> KeyError."""
        alias_map = self._alias_map
        seen: set[str] = set()
        cur = ref
        while cur in alias_map:
            if cur in seen:
                raise KeyError(ref)
            seen.add(cur)
            cur = alias_map[cur]
        if cur not in self._node_by_ref:
            raise KeyError(ref)
        return cur

    def node(self, ref: str) -> PlannedNode:
        """Node for a ref or an alias ref."""
        return self._node_by_ref[self.resolve(ref)]

    def names(self, scope: str) -> tuple[str, ...]:
        """Sorted names visible in `scope`: its nodes and its aliases."""
        return self._names_by_scope.get(scope, ())

    # Lookup indexes over the immutable fields; cached on first use, never part of eq/hash/JSON.
    @functools.cached_property
    def _alias_map(self) -> dict[str, str]:
        return dict(self.aliases)

    @functools.cached_property
    def _node_by_ref(self) -> dict[str, PlannedNode]:
        return {n.ref: n for n in self.nodes}

    @functools.cached_property
    def _names_by_scope(self) -> dict[str, tuple[str, ...]]:
        names: dict[str, set[str]] = {}
        for n in self.nodes:
            names.setdefault(n.scope, set()).add(n.name)
        for alias_ref, _ in self.aliases:
            scope, name = alias_ref.split(".", 1)
            names.setdefault(scope, set()).add(name)
        return {scope: tuple(sorted(v)) for scope, v in names.items()}

    @functools.cached_property
    def _refs_by_contract(self) -> dict[tuple[str, str], tuple[str, ...]]:
        found: dict[tuple[str, str], set[str]] = {}
        for scope, names in self._names_by_scope.items():
            for name in names:
                ref = self.resolve(f"{scope}.{name}")
                found.setdefault((scope, self._node_by_ref[ref].contract), set()).add(ref)
        return {key: tuple(sorted(refs)) for key, refs in found.items()}

    def refs_of(self, scope: str, contract: str) -> tuple[str, ...]:
        """The plan refs that fulfil `contract` in `scope` (shared ones included), sorted."""
        return self._refs_by_contract.get((scope, contract), ())

    def tokens(self, scope: str) -> tuple[str, ...]:
        """Sorted distinct contracts available by name in `scope` (aliases included)."""
        tokens = set()
        for name in self.names(scope):
            tokens.add(self.node(f"{scope}.{name}").contract)
        return tuple(sorted(tokens))

    def scopes(self) -> tuple[str, ...]:
        scopes = {n.scope for n in self.nodes}
        for alias_ref, _ in self.aliases:
            scopes.add(alias_ref.rsplit(".", 1)[0])
        return tuple(sorted(scopes))

    def to_json(self) -> dict:
        return {
            "nodes": [
                {
                    "scope": n.scope,
                    "name": n.name,
                    "contract": n.contract,
                    "provider": n.provider,
                    "impl": n.impl,
                    "config": {k: v for k, v in n.config},
                    "bindings": {k: v for k, v in n.bindings},
                    "why": {
                        "provider": n.why_provider,
                        "bindings": {k: v for k, v in n.why_bindings},
                    },
                    "gives": n.gives.to_json(),
                }
                for n in self.nodes
            ],
            "construction_order": list(self.construction_order),
            "aliases": {k: v for k, v in self.aliases},
            "seams": [
                {
                    "consumer": s.consumer,
                    "slot": s.slot,
                    "provider": s.provider,
                    "expected": list(s.expected),
                    "given": list(s.given),
                }
                for s in self.seams
            ],
            "kinds": list(self.kinds),
        }

    @classmethod
    def from_json(cls, data: dict) -> "TargetPlan":
        nodes = tuple(
            PlannedNode(
                scope=n["scope"],
                name=n["name"],
                contract=n["contract"],
                provider=n["provider"],
                impl=n["impl"],
                config=tuple(sorted(n["config"].items())),
                bindings=tuple(sorted(n["bindings"].items())),
                why_provider=n["why"]["provider"],
                why_bindings=tuple(sorted(n["why"]["bindings"].items())),
                gives=Shape.from_json(n.get("gives", {})),
            )
            for n in data["nodes"]
        )
        seams = tuple(
            Seam(
                consumer=s["consumer"],
                slot=s["slot"],
                provider=s["provider"],
                expected=tuple(s["expected"]),
                given=tuple(s["given"]),
            )
            for s in data["seams"]
        )
        return cls(
            nodes=nodes,
            construction_order=tuple(data["construction_order"]),
            aliases=tuple(sorted(data["aliases"].items())),
            seams=seams,
            kinds=tuple(data.get("kinds", ())),
        )
