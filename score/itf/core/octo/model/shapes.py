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
"""Shapes: what an object offers (`gives`) and what a consumer expects of it, compared as plain data.

A seam is one consumer slot bound to one provider node; the check there is `given ⊇ expected`.
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Literal


@dataclass(frozen=True, order=True)
class Member:
    name: str
    kind: Literal["attr", "call"] = "attr"
    signature: str | None = None
    parameters: tuple[tuple[str, str, bool], ...] | None = None

    def to_json(self) -> dict:
        result = {"name": self.name, "kind": self.kind, "signature": self.signature}
        if self.parameters is not None:
            result["parameters"] = [list(parameter) for parameter in self.parameters]
        return result

    @classmethod
    def from_json(cls, data: dict) -> "Member":
        parameters = data.get("parameters")
        return cls(
            name=data["name"],
            kind=data.get("kind", "attr"),
            signature=data.get("signature"),
            parameters=tuple(tuple(parameter) for parameter in parameters) if parameters is not None else None,
        )


@dataclass(frozen=True)
class Shape:
    members: frozenset[Member] = frozenset()
    protocols: frozenset[str] = frozenset()

    @staticmethod
    def of(*names: str) -> "Shape":
        return Shape(members=frozenset(Member(n) for n in names))

    def satisfies(self, expected: "Shape") -> tuple[bool, frozenset[str]]:
        """Is `self` (given) enough for `expected`? Returns (ok, missing member/protocol names)."""
        missing_members, drift, missing_protocols = classify(self, expected)
        missing = frozenset(missing_members) | frozenset(drift) | frozenset(missing_protocols)
        return (not missing, missing)

    def to_json(self) -> dict:
        return {
            "members": [m.to_json() for m in sorted(self.members, key=lambda m: m.name)],
            "protocols": sorted(self.protocols),
        }

    @classmethod
    def from_json(cls, data: dict) -> "Shape":
        return cls(
            members=frozenset(Member.from_json(m) for m in data.get("members", ())),
            protocols=frozenset(data.get("protocols", ())),
        )


@dataclass(frozen=True)
class Need:
    """One dependency: `slot` must be filled by something fulfilling `contract`, shaped like `expected`."""

    slot: str
    contract: str
    expected: Shape = Shape()

    def to_json(self) -> dict:
        return {"slot": self.slot, "contract": self.contract, "expected": self.expected.to_json()}

    @classmethod
    def from_json(cls, data: dict) -> "Need":
        return cls(
            slot=data["slot"],
            contract=data["contract"],
            expected=Shape.from_json(data.get("expected", {})),
        )


def classify(given: Shape, expected: Shape) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """(missing members, signature drift as "name(sig)", missing protocols), each sorted."""
    given_by_name = {m.name: m for m in given.members}
    missing_members, drift = [], []
    for m in sorted(expected.members, key=lambda m: m.name):
        gm = given_by_name.get(m.name)
        if gm is None:
            missing_members.append(m.name)
        elif m.parameters is not None and (
            gm.kind != "call" or gm.parameters is None or not _accepts_calls(gm.parameters, m.parameters)
        ):
            drift.append(f"{m.name}{_signature(m.parameters)}")
        elif m.signature is not None and gm.signature is not None and m.signature != gm.signature:
            drift.append(f"{m.name}({m.signature})")
    missing_protocols = sorted(p for p in expected.protocols if p not in given.protocols)
    return tuple(missing_members), tuple(drift), tuple(missing_protocols)


def _signature(parameters) -> inspect.Signature:
    return inspect.Signature(
        [
            inspect.Parameter(
                name,
                getattr(inspect.Parameter, kind),
                default=inspect.Parameter.empty if required else None,
            )
            for name, kind, required in parameters
        ]
    )


def _accepts_calls(offered, expected) -> bool:
    given, needed = _signature(offered), _signature(expected)
    for kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
        if any(parameter.kind == kind for parameter in needed.parameters.values()) and not any(
            parameter.kind == kind for parameter in given.parameters.values()
        ):
            return False
    positional = [
        parameter
        for parameter in needed.parameters.values()
        if parameter.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    count_limit = len(positional)
    if any(parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in needed.parameters.values()):
        count_limit = (
            max(
                count_limit,
                sum(
                    parameter.kind
                    in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    )
                    for parameter in given.parameters.values()
                ),
            )
            + 1
        )
    extras = [None]
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in needed.parameters.values()):
        named = {
            parameter.name
            for parameter in needed.parameters.values()
            if parameter.kind != inspect.Parameter.POSITIONAL_ONLY
        }
        extras.extend(name for name in given.parameters if name not in named)
    marker = object()
    for count in range(count_limit + 1):
        for optional in (False, True):
            arguments = [marker] * count
            keywords = {
                parameter.name: marker
                for parameter in needed.parameters.values()
                if parameter.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
                and parameter not in positional[:count]
                and (optional or parameter.default is inspect.Parameter.empty)
            }
            for extra in extras:
                supplied = keywords | ({extra: marker} if extra is not None else {})
                try:
                    needed.bind(*arguments, **supplied)
                except TypeError:
                    continue
                try:
                    given.bind(*arguments, **supplied)
                except TypeError:
                    return False
    return True


# Shapes compare member names (and optionally signatures) as data and never import the provider: this is
# what lets a consumer declare its own Protocol while a pack publishes a different class, with the planner
# checking only that the names line up. No nominal typing across packs, by design.
def shape_of(template, *, signatures: bool = False) -> Shape:
    """Extract the member-name footprint `template` declares, regardless of what kind of type it
    is: `typing.Protocol`, a dataclass, an ABC, a Pydantic model, or a plain class.

    Structural, not nominal — a caller compares the result via `classify()`/`Shape.satisfies()`,
    never via `isinstance`/`issubclass` against `template` itself. `None` and an already-built
    `Shape` pass through unchanged, so this can replace any single-class shape spec a contributor
    already passes to `expect()`/a type annotation without them needing to know which branch fires.
    """
    if template is None:
        return Shape()
    if isinstance(template, Shape):
        return template

    if signatures:
        members = []
        for member in shape_of(template).members:
            if member.name.startswith("_"):
                continue
            method = getattr(template, member.name, None)
            if not callable(method):
                members.append(member)
                continue
            try:
                parameters = list(inspect.signature(method).parameters.values())
            except (TypeError, ValueError):
                members.append(Member(member.name, kind="call"))
                continue
            descriptor = inspect.getattr_static(template, member.name)
            if parameters and parameters[0].name in ("self", "cls") and not isinstance(descriptor, staticmethod):
                parameters = parameters[1:]
            members.append(
                Member(
                    member.name,
                    kind="call",
                    parameters=tuple(
                        (parameter.name, parameter.kind.name, parameter.default is inspect.Parameter.empty)
                        for parameter in parameters
                    ),
                )
            )
        return Shape(members=frozenset(members))

    # typing.Protocol, Python 3.12+: the public, pre-computed attribute list.
    proto_attrs = getattr(template, "__protocol_attrs__", None)
    if proto_attrs is not None:
        return Shape.of(*proto_attrs)

    # Pydantic v2 model: declared fields, plus any methods it adds.
    model_fields = getattr(template, "model_fields", None)
    if model_fields is not None:
        return Shape.of(*model_fields, *_callable_names(template))

    # dataclass: declared fields, plus any methods it adds.
    dc_fields = getattr(template, "__dataclass_fields__", None)
    if dc_fields is not None:
        return Shape.of(*dc_fields, *_callable_names(template))

    # ABC: its abstract methods are the minimal required surface.
    abstract = getattr(template, "__abstractmethods__", None)
    if abstract:
        return Shape.of(*abstract)

    # typing.Protocol, pre-3.12 (no __protocol_attrs__): walk the MRO, stop at Protocol/object.
    if getattr(template, "_is_protocol", False):
        return Shape.of(*_mro_members(template, stop_names=frozenset({"Protocol", "object"})))

    # Plain concrete class: annotations + callable methods declared in its own MRO.
    return Shape.of(*_mro_members(template, stop_names=frozenset({"object"})))


def _callable_names(cls) -> frozenset[str]:
    """Public callable names defined directly on `cls` (not inherited from `object`)."""
    names: set[str] = set()
    for c in getattr(cls, "__mro__", (cls,)):
        if c is object:
            break
        for name, val in c.__dict__.items():
            if not name.startswith("_") and callable(val):
                names.add(name)
    return frozenset(names)


def _mro_members(cls, *, stop_names: frozenset[str]) -> frozenset[str]:
    """Annotated attribute names and callable method names, walking the MRO until a stop name."""
    own: set[str] = set()
    for c in getattr(cls, "__mro__", (cls,)):
        if c.__name__ in stop_names:
            break
        for name in c.__dict__.get("__annotations__", {}):
            if not name.startswith("_"):
                own.add(name)
        for name, val in c.__dict__.items():
            if not name.startswith("_") and callable(val):
                own.add(name)
    return frozenset(own)
