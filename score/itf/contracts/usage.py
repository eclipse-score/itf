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
"""The contract map: every contract name in use, from the loaded factories and actions and from tests.

`contract_map(parts, tests=None, definitions=None)` returns, per contract name, who offers it (label and the
members it publishes), who needs it (label and the members it expects), which tests ask for it, its definition
if there is one, and every disagreement between them. It reads declarations only (data), never runs anything.

`parts` is a catalog (anything with `.factories` and `.action_descs` dicts) or an iterable of factory and action
descriptors. `tests` is an iterable of requirements, or of `(test id, requirement)` pairs; a requirement has
`role`, `contract`, `shape`. `definitions` is a dict or a list of `Definition` (a list can hold two for one name).

`skeleton_from_usage(name, map)` builds a definition skeleton (a dict, ready for `yaml.safe_dump`) from the
shapes observed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from score.itf.core.engine.publish import split_major


@dataclass(frozen=True)
class Disagreement:
    kind: str  # missing-member | missing-definition-member | two-definitions | major-mismatch
    message: str


@dataclass
class ContractEntry:
    name: str
    kind: str = "capability"
    offerers: list = field(default_factory=list)  # (label, members, major or None)
    needers: list = field(default_factory=list)  # (label, slot, expected members, major or None)
    tests: list = field(default_factory=list)  # (test id, role, members, major)
    definition: object = None
    definitions: list = field(default_factory=list)
    disagreements: list = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "contract": self.name,
            "kind": self.kind,
            "offered_by": [{"label": l, "shape": list(m), "major": mj} for l, m, mj in self.offerers],
            "needed_by": [{"label": l, "slot": s, "expects": list(m), "major": mj} for l, s, m, mj in self.needers],
            "tests": [{"test": t, "role": r, "shape": list(m), "major": major} for t, r, m, major in self.tests],
            "defined": self.definition is not None,
            "disagreements": [{"kind": d.kind, "message": d.message} for d in self.disagreements],
        }


def _members(shape) -> tuple[str, ...]:
    members = getattr(shape, "members", shape) or ()
    return tuple(sorted(getattr(m, "name", m) for m in members if not str(getattr(m, "name", m)).startswith("_")))


def _descriptors(parts) -> list:
    if hasattr(parts, "factories") and hasattr(parts, "action_descs"):
        return [*parts.factories.values(), *parts.action_descs.values()]
    return list(parts)


def _entry(found: dict, name: str, kind: str) -> ContractEntry:
    entry = found.setdefault(name, ContractEntry(name, kind))
    if kind == "state":
        entry.kind = "state"
    return entry


def _add_need(found: dict, label: str, need, major) -> None:
    _entry(found, need.contract, "capability").needers.append((label, need.slot, _members(need.expected), major))


def _add_factory(found: dict, part) -> None:
    _entry(found, part.contract, "capability").offerers.append((part.label, _members(part.gives), part.major))
    for need in part.needs:
        _add_need(found, part.label, need, part.need_majors.get(need.slot))


def _add_action(found: dict, part) -> None:
    for state in (part.state, *part.also):
        name, major = split_major(state.rpartition(":")[2])
        _entry(found, name, "state").offerers.append((part.label, (), major))
    for relation in ("after", "breaks"):
        for state in getattr(part, relation, ()):
            name, major = split_major(state.rpartition(":")[2])
            _entry(found, name, "state").needers.append((part.label, relation, (), major))
    for need in part.uses:
        _add_need(found, part.label, need, part.need_majors.get(need.slot))


def _add_tests(found: dict, tests) -> None:
    for item in tests or ():
        test_id, requirement = item if isinstance(item, tuple) else ("", item)
        if getattr(requirement, "contract", None):
            _entry(found, requirement.contract, "capability").tests.append(
                (test_id, requirement.role, _members(requirement.shape), getattr(requirement, "major", None))
            )


def _add_expectations(found: dict, parts) -> None:
    for expectation in getattr(parts, "expectations", ()):
        name, major = split_major(expectation.contract)
        _entry(found, name, "capability").needers.append(
            (expectation.origin, "itf_expect", _members(expectation.shape), major)
        )


def _add_definitions(found: dict, definitions) -> None:
    for definition in definitions.values() if isinstance(definitions, dict) else definitions or ():
        entry = _entry(found, definition.contract, definition.kind)
        entry.definitions.append(definition)
        entry.definition = entry.definition or definition


def contract_map(parts, tests=None, definitions=None) -> dict[str, ContractEntry]:
    found: dict[str, ContractEntry] = {}
    for part in _descriptors(parts):
        (_add_factory if hasattr(part, "contract") else _add_action)(found, part)
    _add_expectations(found, parts)
    _add_tests(found, tests)
    _add_definitions(found, definitions)
    for entry in found.values():
        _compare(entry)
    return dict(sorted(found.items()))


def _two_definitions(entry: ContractEntry) -> list[Disagreement]:
    if len(entry.definitions) < 2:
        return []
    where = ", ".join(d.source or "?" for d in entry.definitions)
    return [Disagreement("two-definitions", f"{entry.name} is defined {len(entry.definitions)} times: {where}")]


def _unoffered_members(entry: ContractEntry) -> list[Disagreement]:
    """A member a needer or a test relies on that no offerer has (nothing to say when nobody offers the contract)."""
    if not entry.offerers:
        return []
    offered = {m for _, members, _ in entry.offerers for m in members}
    return _needers_missing(entry, offered) + _tests_missing(entry, offered)


def _needers_missing(entry: ContractEntry, offered: set) -> list[Disagreement]:
    offerers = ", ".join(l for l, _, _ in entry.offerers)
    return [
        Disagreement(
            "missing-member",
            f"{label} (slot {slot}) expects {entry.name}.{member}, which no offerer has ({offerers})",
        )
        for label, slot, expected, _ in entry.needers
        for member in expected
        if member not in offered
    ]


def _tests_missing(entry: ContractEntry, offered: set) -> list[Disagreement]:
    return [
        Disagreement("missing-member", f"test {test_id or role} requires {entry.name}.{member}, which no offerer has")
        for test_id, role, shape, _ in entry.tests
        for member in shape
        if member not in offered
    ]


def _unoffered_majors(entry: ContractEntry) -> list[Disagreement]:
    if not entry.offerers:
        return []
    majors_offered = {m for _, _, m in entry.offerers if m is not None}
    offered = ", ".join(f"@{m}" for m in sorted(majors_offered)) or "(no majors declared)"
    return [
        Disagreement("major-mismatch", f"{label} (slot {slot}) expects {entry.name}@{major}, offered: {offered}")
        for label, slot, _, major in entry.needers
        if major is not None and major not in majors_offered
    ] + [
        Disagreement("major-mismatch", f"test {test_id or role} expects {entry.name}@{major}, offered: {offered}")
        for test_id, role, _, major in entry.tests
        if major is not None and major not in majors_offered
    ]


def _against_definition(entry: ContractEntry) -> list[Disagreement]:
    """Definitions bound offered majors; capability definitions also require members."""
    definition = entry.definition
    if definition is None:
        return []
    members = _lacking_required(entry, definition) if definition.kind == "capability" else []
    return members + _ahead_of_version(entry, definition)


def _lacking_required(entry: ContractEntry, definition) -> list[Disagreement]:
    required = [m.name for m in definition.members if m.required]
    return [
        Disagreement(
            "missing-definition-member",
            f"{label} offers {entry.name} without {member}, which its definition requires",
        )
        for label, members, _ in entry.offerers
        for member in required
        if member not in members
    ]


def _ahead_of_version(entry: ContractEntry, definition) -> list[Disagreement]:
    return [
        Disagreement(
            "major-mismatch",
            f"{label} offers {entry.name}@{major}, but the definition's version is {definition.version}",
        )
        for label, _, major in entry.offerers
        if major is not None and major > definition.version
    ]


def _compare(entry: ContractEntry) -> None:
    for check in (_two_definitions, _unoffered_members, _unoffered_majors, _against_definition):
        entry.disagreements.extend(check(entry))


def _skeleton_members(entry: ContractEntry) -> list[dict]:
    """Members expected by needers and tests (required), then those only offered (optional)."""
    expected = _expected_members(entry)
    published = sorted({m for _, members, _ in entry.offerers for m in members})
    return [_skeleton_member(m, m in expected) for m in sorted(expected) + [m for m in published if m not in expected]]


def _expected_members(entry: ContractEntry) -> set:
    return {m for _, _, members, _ in entry.needers for m in members} | {
        m for _, _, members, _ in entry.tests for m in members
    }


def _skeleton_member(name: str, required: bool) -> dict:
    return {"name": name, "signature": "TODO", "semantics": "TODO", **({} if required else {"required": False})}


def _capability_part(entry: ContractEntry) -> dict:
    """The suggested role (the alphabetically first one tests use) and the members, when there are any."""
    roles = sorted({r for _, r, _, _ in entry.tests})
    members = _skeleton_members(entry)
    return ({"role": roles[0]} if roles else {}) | ({"members": members} if members else {})


def skeleton_from_usage(name: str, contracts: dict[str, ContractEntry]) -> dict:
    """A definition skeleton for `name`: the members observed (expected by needers and tests, published by
    offerers; the latter only are optional), the role most tests use, the major in use."""
    if name not in contracts:
        raise KeyError(f"{name!r} is not in use; contracts in use: {', '.join(contracts) or '(none)'}")
    entry = contracts[name]
    majors = [m for _, _, m in entry.offerers if m is not None] + [m for _, _, _, m in entry.needers if m is not None]
    skeleton = {
        "contract": name,
        "kind": entry.kind,
        "version": max(majors, default=1),
        "summary": "TODO",
        "description": "TODO",
    }
    if entry.kind == "capability":
        skeleton.update(_capability_part(entry))
    skeleton["guarantees"] = ["TODO"]
    return skeleton
