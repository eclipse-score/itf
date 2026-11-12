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
"""`@itf.requires` and gating tests against the plan.

A test asks for a role: `@itf.requires("command")` means the target has a role `command`; `contract=` and
`shape=` narrow it: `@itf.requires("command", contract="exec.command", shape=["exec"])`. The test then uses
`target.command`. A test is deselected, before anything is built, with a reason naming what the target has:
the role is missing, it has another contract, or it lacks members. Which role names a project uses is the
project's convention; `itf contracts check` can enforce it.

A requirement can also sit on a test class (`@itf.requires` on the class; subclasses inherit it), on a module
(`itf_requires = itf.requires(...)`, or a list of them) or on a package (the same line in its `__init__.py`). A
test needs every requirement on it and above it.
"""

from __future__ import annotations

import sys
import json
from dataclasses import dataclass, replace

from .engine.publish import split_major
from .engine.scopes import ROOT
from .octo import Diagnostic, Shape, shape_mismatches, shape_of
from .octo.model.shapes import classify

_MARK = "__itf_requirements__"
MODULE_ATTR = "itf_requires"  # a module's or a package's requirements


@dataclass(frozen=True)
class Requirement:
    role: str
    contract: str | None = None
    shape: tuple[str, ...] | Shape | None = None
    scope: str | None = None
    major: int | None = None


@dataclass(frozen=True)
class Definition:
    """What a session may know about a defined contract, handed in (the engine never needs it)."""

    contract: str
    version: int | None = None
    stability: str = "stable"  # experimental | stable | deprecated
    replaced_by: str | None = None


def requires(role: str, contract: str | None = None, shape=None, scope: str | None = None):
    """The test needs the role `role` of the target (`target.<role>`), optionally of `contract` (with `@<major>`)
    and offering the members in `shape`; `scope` names a scope instead of the root.
    A consumer-owned Protocol as `shape` checks callable parameters and supplies its
    __contract__; a member-name list remains a weaker, backwards-compatible check."""
    if not isinstance(role, str) or not role:
        raise TypeError("@itf.requires takes a role name, for example @itf.requires('command')")
    if isinstance(shape, str):
        raise TypeError("shape is a list of member names, not a string")
    if isinstance(shape, type):
        if not getattr(shape, "_is_protocol", False):
            raise TypeError("a strict shape must be a Protocol")
        declared = getattr(shape, "__contract__", None)
        if declared and contract and split_major(declared) != split_major(contract):
            raise ValueError(f"Protocol contract {declared!r} disagrees with {contract!r}")
        contract = contract or declared
        shape = shape_of(shape, signatures=True)
    elif not isinstance(shape, Shape):
        shape = tuple(shape) if shape else None
    name, major = split_major(contract) if contract else (None, None)
    return Requires(Requirement(role, name, shape, scope, major))


@dataclass(frozen=True)
class Requires:
    """What `itf.requires(...)` returns: a decorator for a test function or class, and the value of a module's
    or a package's `itf_requires`."""

    requirement: Requirement

    def __call__(self, test):
        setattr(test, _MARK, getattr(test, _MARK, ()) + (self.requirement,))
        return test


def get_requirements(func) -> tuple[Requirement, ...]:
    return getattr(func, _MARK, ())


def requirements_of(func, cls=None, module=None) -> tuple[Requirement, ...]:
    """Every requirement a test has: its packages' (outermost first), its module's, its class's, its own."""
    found: list[Requirement] = []
    if module is not None:
        parts = module.__name__.split(".")
        for i in range(1, len(parts)):
            found += _module_requirements(sys.modules.get(".".join(parts[:i])))
        found += _module_requirements(module)
    if cls is not None:
        found += getattr(cls, _MARK, ())
    found += get_requirements(func) if func is not None else ()
    return tuple(dict.fromkeys(found))


def _module_requirements(module) -> list[Requirement]:
    value = getattr(module, MODULE_ATTR, ()) if module is not None else ()
    items = value if isinstance(value, (list, tuple)) else [value]
    if not all(isinstance(item, Requires) for item in items):
        raise TypeError(f"{module.__name__}.{MODULE_ATTR} must be itf.requires(...) or a list of them, got {value!r}")
    return [item.requirement for item in items]


@dataclass(frozen=True)
class GatingDecision:
    selected: bool
    reason: str = ""
    status: str = "compatible"
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True)
class RequirementProfile:
    requirement: Requirement
    decision: GatingDecision
    tests: tuple[str, ...]
    provider: str | None = None
    offered_contract: str | None = None
    offered_major: int | None = None
    given: Shape | None = None

    def to_json(self) -> dict:
        expected = self.requirement.shape
        return {
            "expected": expected.to_json() if isinstance(expected, Shape) else list(expected or ()),
            "provider": self.provider,
            "offered_contract": self.offered_contract,
            "offered_major": self.offered_major,
            "given": self.given.to_json() if self.given is not None else None,
            "status": self.decision.status,
            "reason": self.decision.reason,
            "tests": list(self.tests),
            "diagnostics": [
                {
                    "code": diagnostic.code,
                    "subject": diagnostic.subject,
                    "gate": diagnostic.gate,
                    "evidence": [list(pair) for pair in diagnostic.evidence],
                }
                for diagnostic in self.decision.diagnostics
            ],
        }


@dataclass(frozen=True)
class RequirementGroup:
    scope: str
    role: str
    contract: str | None
    major: int | None
    profiles: tuple[RequirementProfile, ...]

    @property
    def status(self) -> str:
        statuses = {profile.decision.status for profile in self.profiles}
        return next(iter(statuses)) if len(statuses) == 1 else "partial"

    def to_json(self) -> dict:
        return {
            "scope": self.scope,
            "role": self.role,
            "contract": self.contract,
            "major": self.major,
            "status": self.status,
            "profiles": [profile.to_json() for profile in self.profiles],
        }


@dataclass(frozen=True)
class PreflightReport:
    decisions: dict[str, GatingDecision]
    groups: tuple[RequirementGroup, ...]

    @property
    def blocking(self) -> tuple[RequirementProfile, ...]:
        return tuple(
            profile
            for group in self.groups
            for profile in group.profiles
            if profile.decision.status in ("incompatible", "unknown")
        )

    def to_json(self) -> dict:
        return {"groups": [group.to_json() for group in self.groups]}

    def render(self, *, blocking_only: bool = False) -> str:
        lines = ["ITF compatibility preflight:"]
        for group in self.groups:
            profiles = tuple(
                profile
                for profile in group.profiles
                if not blocking_only or profile.decision.status in ("incompatible", "unknown")
            )
            if not profiles:
                continue
            label = "target" if group.scope == ROOT else f"target.{group.scope}"
            contract = group.contract or "any contract"
            if group.major is not None:
                contract += f"@{group.major}"
            lines.append(f"  {label}.{group.role} / {contract}: {group.status}")
            for profile in profiles:
                lines.append(
                    f"    {profile.decision.status}: {len(profile.tests)} test(s); provider {profile.provider or '(none)'}"
                )
                if profile.decision.reason:
                    lines.append(f"      {profile.decision.reason}")
                if blocking_only:
                    lines.extend(f"      {test}" for test in profile.tests)
        return "\n".join(lines)


def preflight(requirements: dict, target_plan, factory_majors: dict | None = None) -> PreflightReport:
    known = {ROOT, *target_plan.scopes()}
    evaluated = {}
    tests_by_profile: dict[Requirement, list[str]] = {}
    decisions = {}
    for test_id in sorted(requirements):
        test_decisions = []
        normalized = (replace(requirement, scope=requirement.scope or ROOT) for requirement in requirements[test_id])
        for requirement in dict.fromkeys(normalized):
            if requirement not in evaluated:
                scope = requirement.scope or ROOT
                evaluated[requirement] = (
                    evaluate(requirement, target_plan, scope, factory_majors)
                    if scope in known
                    else GatingDecision(False, f"target has no scope {requirement.scope!r}", "not_applicable")
                )
            tests_by_profile.setdefault(requirement, []).append(test_id)
            test_decisions.append(evaluated[requirement])
        decisions[test_id] = next(
            (decision for decision in test_decisions if not decision.selected), GatingDecision(True)
        )
    families = {}
    for requirement, tests in tests_by_profile.items():
        scope = requirement.scope or ROOT
        node = (
            target_plan.node(f"{scope}.{requirement.role}")
            if scope in known and requirement.role in target_plan.names(scope)
            else None
        )
        profile = RequirementProfile(
            requirement,
            evaluated[requirement],
            tuple(tests),
            node.provider if node else None,
            node.contract if node else None,
            (factory_majors or {}).get(node.provider) if node else None,
            node.gives if node else None,
        )
        key = (scope, requirement.role, requirement.contract, requirement.major)
        families.setdefault(key, []).append(profile)
    groups = tuple(
        RequirementGroup(
            *key, tuple(sorted(families[key], key=lambda profile: json.dumps(profile.to_json(), sort_keys=True)))
        )
        for key in sorted(families, key=lambda key: (key[0], key[1], key[2] or "", key[3] or 0))
    )
    return PreflightReport(decisions, groups)


def _wrong_contract(requirement: Requirement, node, where: str, factory_majors) -> str | None:
    if requirement.contract is None or node.contract == requirement.contract:
        return None
    return f"{where} ({node.provider}) is {node.contract!r}, the test requires {requirement.contract!r}"


def _wrong_major(requirement: Requirement, node, where: str, factory_majors) -> str | None:
    offered = (factory_majors or {}).get(node.provider)
    if requirement.major is None or offered == requirement.major:
        return None
    if offered is None:
        return f"{where} ({node.provider}) declares no contract major, the test requires @{requirement.major}"
    return f"{where} ({node.provider}) offers @{offered}, the test requires @{requirement.major}"


def _missing_members(requirement: Requirement, node, where: str, factory_majors) -> str | None:
    if isinstance(requirement.shape, Shape):
        missing, drift, protocols = classify(node.gives, requirement.shape)
        problems = []
        if missing:
            problems.append(f"lacks member(s): {', '.join(missing)}")
        if drift:
            problems.append(f"incompatible signature(s): {', '.join(drift)}")
        if protocols:
            problems.append(f"lacks protocol(s): {', '.join(protocols)}")
        return f"{where} ({node.provider}) {'; '.join(problems)}" if problems else None
    have = {m.name for m in node.gives.members}
    missing = [m for m in requirement.shape or () if m not in have]
    return f"{where} ({node.provider}) lacks member(s): {', '.join(missing)}" if missing else None


def evaluate(requirement: Requirement, target_plan, scope: str, factory_majors: dict | None = None) -> GatingDecision:
    label = "target" if scope == ROOT else f"target.{scope}"
    role = requirement.role
    names = target_plan.names(scope)
    if role not in names:
        return GatingDecision(
            False, f"{label} has no role {role!r}; roles: {', '.join(names) or '(none)'}", "not_applicable"
        )
    node = target_plan.node(f"{scope}.{role}")
    for rule in (_wrong_contract, _wrong_major, _missing_members):
        reason = rule(requirement, node, f"{label}.{role}", factory_majors)
        if reason is not None:
            if rule is not _missing_members:
                status = (
                    "unknown"
                    if rule is _wrong_major and (factory_majors or {}).get(node.provider) is None
                    else "not_applicable"
                )
                return GatingDecision(False, reason, status)
            expected = (
                requirement.shape if isinstance(requirement.shape, Shape) else Shape.of(*(requirement.shape or ()))
            )
            diagnostics = tuple(shape_mismatches(f"{scope}.{role}", node.gives, expected, gate=1))
            given = {member.name: member for member in node.gives.members}
            failed = [
                member for member in expected.members if not node.gives.satisfies(Shape(members=frozenset({member})))[0]
            ]
            if failed and all(
                member.parameters is not None
                and member.name in given
                and given[member.name].parameters is None
                and given[member.name].kind == "call"
                for member in failed
            ):
                return GatingDecision(False, reason + "; callable metadata is unavailable", "unknown", diagnostics)
            return GatingDecision(False, reason, "incompatible", diagnostics)
    return GatingDecision(True)


def deprecations(target_plan, definitions: dict | None) -> list[str]:
    """Plan-time warnings: a role's contract is defined as deprecated (only when definitions are loaded)."""
    found = []
    for node in target_plan.nodes:
        definition = (definitions or {}).get(node.contract)
        if definition is not None and definition.stability == "deprecated":
            use = f"; use {definition.replaced_by!r}" if definition.replaced_by else ""
            found.append(f"role {node.name} ({node.provider}) is {node.contract!r}, which is deprecated{use}")
    return found
