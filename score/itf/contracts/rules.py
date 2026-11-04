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
"A project's rules over contracts, checked in a pipeline: `check(rules, contract_map, target files)`.\n\nA contract rules file (YAML, or a mapping):\n\n    namespaces:           # contracts in these namespaces must have a definition (`acme` for acme/power.relay;\n                          # a name without `/` is its first segment: `exec` for exec.command)\n      - exec\n      - platform\n    roles:                # role -> the contract it must always be\n      command: exec.command\n      platform: platform.instance\n    forbid_stability:     # no target file may use a contract defined with these stabilities\n      - deprecated\n\n`target files` is an iterable of target plans, or of `(name, {role: contract})` pairs (`roles_of_plan` makes\nthose). `check` returns the violations; an empty list means the rules hold (the CLI exits 1 otherwise)."

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


from score.itf.core.engine.yaml_text import safe_load as yaml_safe_load

from score.itf.core.engine.scopes import ROOT

from .usage import ContractEntry

RULES = ('namespaces', 'roles', 'forbid_stability')


def namespace_of(name: str) -> str:
    """`acme/power.relay` -> `acme`; a name without `/` -> its first segment (`exec.command` -> `exec`)."""
    return name.split("/", 1)[0] if "/" in name else name.split(".", 1)[0]


@dataclass(frozen=True)
class Violation:
    rule: str  # namespaces | roles | forbid_stability
    message: str


def roles_of_plan(plan) -> dict[str, str]:
    """`{role: contract}` of a target plan; a role of a scope is `scope.role`."""
    out = {}
    for node in plan.nodes:
        scope = "" if node.scope == ROOT else f"{node.scope}."
        out[f"{scope}{node.name}"] = node.contract
    return out


def _rules(rules) -> dict:
    if isinstance(rules, dict):
        data = rules
    else:
        data = yaml_safe_load(Path(rules).read_text(encoding="utf-8") if Path(str(rules)).is_file() else str(rules))
    data = data or {}
    unknown = sorted(set(data) - set(RULES))
    if unknown:
        raise ValueError(f"rules: unknown rule(s) {', '.join(unknown)}; the rules are {', '.join(RULES)}")
    return data


def check(rules, contracts: dict[str, ContractEntry], target_files=()) -> list[Violation]:
    rules = _rules(rules)
    found: list[Violation] = []
    for name, entry in contracts.items():
        if namespace_of(name) in (rules.get("namespaces") or ()) and entry.definition is None:
            found.append(Violation("namespaces", f"{name} is in use but has no definition"))
        stability = getattr(entry.definition, "stability", None)
        if stability in (rules.get("forbid_stability") or ()):
            found.append(Violation("forbid_stability", f"{name} is {stability}, which the rules forbid"))
    for item in target_files:
        label, roles = item if isinstance(item, tuple) else ("target", roles_of_plan(item))
        for role, contract in sorted(roles.items()):
            wanted = (rules.get("roles") or {}).get(role.rpartition(".")[2])
            if wanted is not None and wanted != contract:
                found.append(
                    Violation("roles", f"{label}: role {role} is {contract}, the rules say it is always {wanted}")
                )
    return found


def load_rules(rules) -> dict:
    """The rules of a contract rules file (or mapping); an unknown rule is an error naming the known ones."""
    return _rules(rules)
