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
"Contract definitions: an optional library. ITF knows no contracts; a contract is whatever name two\nparts agree on. A definition adds meaning, a version, members, guarantees, a suggested role, a stability and a\n\nDefinitions are YAML files (`contracts: - contract: exec.command, kind: capability, version: 1, summary, ...`).\nBuilt-in packs list individual `$ref` files pointing to the shared `definitions/` directory, one specification\nper contract. References resolve from the declaring file; repeated references to one source are loaded once.\nThey are found in three places, merged by `load_list()`:\n\n* the `contracts/` directory of every pack (the ITF team's supported definitions ship with the packs that use them),\n* the directories listed in `ITF_CONTRACTS_PATH`,\n* installed distributions with an entry point in the group `score_itf.contracts` (the value names a package,\n  or a callable returning directories, holding YAML files).\n\nFields: `contract` (the name), `kind` (capability | state), `version`, `summary`, `description`, `members`\n(`name`, `signature`, `semantics`), `guarantees`, `role` (the role name suggested in target files),\ncontract name), `see_also`, `probe`. Two definitions of one name are not an error here: `contract_map` reports\nthem. `definitions()` is the forgiving view a session wants: name -> the first definition."

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.resources
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from score.itf.core.engine.yaml_text import safe_load as yaml_safe_load

KINDS = ("capability", "state")
STABILITIES = ("experimental", "stable", "deprecated")
ENTRY_POINT_GROUP = "score_itf.contracts"
PATH_VARIABLE = "ITF_CONTRACTS_PATH"
PACKS_PACKAGE = "score.itf.packs"
logger = logging.getLogger(__name__)


class ContractError(ValueError):
    """A definition file is malformed."""


@dataclass(frozen=True)
class Member:
    name: str
    signature: str = ""
    semantics: str = ""
    required: bool = True  # False: a provider may omit it; tests gate on it with `shape=`


@dataclass(frozen=True)
class Definition:
    contract: str
    kind: str
    version: int = 1
    summary: str = ''
    description: str = ''
    members: tuple[Member, ...] = ()
    guarantees: tuple[str, ...] = ()
    role: str | None = None
    stability: str = 'stable'
    replaced_by: str | None = None
    see_also: tuple[str, ...] = ()
    probe: str | None = None
    source: str = ''

    @property
    def member_names(self) -> tuple[str, ...]:
        return tuple((m.name for m in self.members))


def _text(value) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def _definition(entry: dict, source: str) -> Definition:
    name = entry.get('contract')
    if not isinstance(name, str) or not name:
        raise ContractError(f'{source}: an entry needs `contract:` (its name)')
    kind = entry.get('kind')
    if kind not in KINDS:
        raise ContractError(f'{source}: {name}: kind must be one of {KINDS}, got {kind!r}')
    stability = entry.get('stability', 'stable')
    if stability not in STABILITIES:
        raise ContractError(f'{source}: {name}: stability must be one of {STABILITIES}, got {stability!r}')
    members = []
    for member in entry.get('members') or ():
        if not isinstance(member, dict) or not member.get('name'):
            raise ContractError(f'{source}: {name}: a member is a mapping with a name')
        members.append(Member(member['name'], _text(member.get('signature')), _text(member.get('semantics')), bool(member.get('required', True))))
    if kind == 'state' and members:
        raise ContractError(f'{source}: {name}: a state has no members')
    version = entry.get('version', 1)
    if type(version) is not int or version < 1:
        raise ContractError(f'{source}: {name}: version must be a positive integer major, got {version!r}')
    return Definition(contract=name, kind=kind, version=version, summary=_text(entry.get('summary')), description=_text(entry.get('description')), members=tuple(members), guarantees=tuple((_text(g) for g in entry.get('guarantees') or ())), role=entry.get('role'), stability=stability, replaced_by=entry.get('replaced_by'), see_also=tuple(entry.get('see_also') or ()), probe=_text(entry['probe']) if entry.get('probe') else None, source=source)


def _read_file(path: Path, label, loaded: set[Path], visiting=()) -> list[Definition]:
    key = path.resolve()
    where = f"{label or path.parent}: {path.name}"
    if key in visiting:
        raise ContractError(f"{where}: contract reference cycle")
    if key in loaded:
        return []
    try:
        document = yaml_safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ContractError(f"{where}: cannot read contract definition: {exc}") from exc
    if not isinstance(document, dict):
        raise ContractError(f"{where}: expected a mapping")
    if "$ref" in document:
        reference = document["$ref"]
        if set(document) != {"$ref"} or not isinstance(reference, str) or not reference.strip():
            raise ContractError(f"{where}: $ref must stand alone and name a contract YAML file")
        found = _read_file(path.parent / reference, None, loaded, (*visiting, key))
    else:
        canonical = Path(__file__).parent / "definitions" / key.name
        if canonical.is_file() and key == canonical.resolve():
            where = f"score.itf.contracts.definitions: {key.name}"
        found = [_definition(entry, where) for entry in document.get("contracts") or ()]
    loaded.add(key)
    return found


def read_directory(directory: Path, label: str | None = None, *, _loaded=None) -> list[Definition]:
    loaded = set() if _loaded is None else _loaded
    return [
        definition
        for path in sorted(Path(directory).glob("*.yaml"))
        for definition in _read_file(path, label or str(directory), loaded)
    ]


def _pack_directories() -> list[Path]:
    try:
        package = importlib.import_module(PACKS_PACKAGE)
    except ImportError:
        return []
    found = []
    for root in getattr(package, "__path__", ()):
        found += sorted(p / "contracts" for p in Path(root).iterdir() if (p / "contracts").is_dir())
    return found


def _entry_point_directories() -> list[Path]:
    found = []
    for ep in sorted(importlib.metadata.entry_points(group=ENTRY_POINT_GROUP), key=lambda e: (e.name, e.value)):
        try:
            value = ep.load()
            if callable(value) and not isinstance(value, type(importlib)):
                found += [Path(p) for p in value()]
            elif isinstance(value, (str, Path)):
                found.append(Path(value))
            else:
                found.append(Path(str(importlib.resources.files(value))))
        except Exception as exc:  # noqa: BLE001
            raise ContractError(f"entry point {ep.name}={ep.value}: cannot read definitions: {exc}") from exc
    return found


def load_list(extra=()) -> list[Definition]:
    """Distinct definitions, duplicates included; repeated references to one source are loaded once."""
    directories = [*_pack_directories(), *_entry_point_directories()]
    for entry in filter(None, os.environ.get(PATH_VARIABLE, "").split(os.pathsep)):
        if not Path(entry).is_dir():
            raise ContractError(f"{PATH_VARIABLE}: {entry!r} is not a directory")
        directories.append(Path(entry))
    directories += [Path(d) for d in extra]
    found: list[Definition] = []
    loaded: set[Path] = set()
    for directory in directories:
        found += read_directory(directory, _loaded=loaded)
    return found


def load(extra=()) -> dict[str, Definition]:
    """name -> definition; where two sources define one name, the first wins."""
    merged: dict[str, Definition] = {}
    for definition in load_list(extra):
        merged.setdefault(definition.contract, definition)
    return merged


from .usage import ContractEntry, Disagreement, contract_map, skeleton_from_usage  # noqa: E402
from .rules import Violation, check, roles_of_plan  # noqa: E402

__all__ = [
    "ContractEntry",
    "ContractError",
    "Definition",
    "Disagreement",
    "Member",
    "Violation",
    "check",
    "contract_map",
    "load",
    "load_list",
    "read_directory",
    "roles_of_plan",
    "skeleton_from_usage",
]
