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
"""What the loaded packs and the tests say about contracts, as plain data: the input of `itf contracts map`, the
catalog page and the reference.

`load_catalog(packs, roots)` imports packs the way a session does (from their names) and publishes what their
factories and actions declare; nothing is constructed. `collect_requirements(paths)` reads `@itf.requires(...)`
decorators from test files without importing them. `inventory(...)` joins both with the contract definitions
and the disagreements `contract_map` finds, in a JSON-shaped dictionary.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib.util
from pathlib import Path


from score.itf.core.engine.yaml_text import safe_load as yaml_safe_load

from . import Definition, load_list
from .usage import contract_map


@dataclasses.dataclass(frozen=True)
class ObservedRequirement:
    """A requirement read from a decorator: no import of the test, no `Requirement` of the core."""

    role: str
    contract: str | None = None
    shape: tuple[str, ...] = ()
    scope: str | None = None


# ---- packs ----------------------------------------------------------------------------------------------------


def known_packs() -> tuple[str, ...]:
    from score.itf.core.engine import packs

    return packs.known()


def load_catalog(packs, roots=(), modules=None):
    """(catalog, errors): the factories and actions of `packs` (names) and of the `roots` (modules playing the
    project's policy). A pack that cannot be imported is an error line, not an exception."""
    from score.itf.core.engine import packs as pack_loader
    from score.itf.core.engine.publish import publish
    from score.itf.core.engine.registry import expand, register_modules
    from score.itf.core.session import _roots

    entries, errors = [], []
    for name in packs:
        try:
            entries.append(pack_loader.load(name, modules))
        except Exception as exc:  # noqa: BLE001 - a missing dependency of one pack must not hide the others
            errors.append(f"pack {name} could not be loaded: {type(exc).__name__}: {exc}")
    registry = register_modules([*expand(entries), *_roots(roots)])
    return publish(registry), errors


def _pack_location(name: str) -> Path | None:
    spec = importlib.util.find_spec(f"score.itf.packs.{name}")
    location = next(iter(spec.submodule_search_locations or ()), None) if spec else None
    return Path(location) if location is not None else None


def _first_paragraph(text: str) -> str:
    """The first paragraph of a README: after the license comment, headings and bold lead lines."""
    paragraph: list[str] = []
    in_comment = False
    for line in text.splitlines():
        if line.startswith("<!--"):
            in_comment = True
        if in_comment:
            in_comment = "-->" not in line
            continue
        if line.startswith(("#", "**")) or not line.strip():
            if paragraph:
                break
            continue
        paragraph.append(line.strip())
    return " ".join(paragraph)


def pack_info(name: str) -> dict:
    """`version` and `prerequisites` from the pack's `pack.yaml`, and the first paragraph of its README."""
    info = {"name": name, "version": "", "prerequisites": [], "summary": ""}
    location = _pack_location(name)
    if location is None:
        return info
    meta = location / "pack.yaml"
    if meta.is_file():
        data = yaml_safe_load(meta.read_text(encoding="utf-8")) or {}
        info["version"] = str(data.get("version", ""))
        info["prerequisites"] = [str(p) for p in data.get("prerequisites") or ()]
    readme = location / "README.md"
    if readme.is_file():
        info["summary"] = _first_paragraph(readme.read_text(encoding="utf-8"))
    return info


# ---- tests ----------------------------------------------------------------------------------------------------


def _constant(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _argument(call: ast.Call, position: int, keyword: str):
    """The node of a call's positional argument `position`, else of its keyword `keyword`, else None."""
    if len(call.args) > position:
        return call.args[position]
    return next((k.value for k in call.keywords if k.arg == keyword), None)


def _requirement(call: ast.Call) -> ObservedRequirement | None:
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    if name != "requires" or not call.args or _constant(call.args[0]) is None:
        return None
    contract = _constant(_argument(call, 1, "contract"))
    scope = _constant(next((k.value for k in call.keywords if k.arg == "scope"), None))
    shape = _shape_of(_argument(call, 2, "shape"))
    return ObservedRequirement(_constant(call.args[0]), contract.split("@")[0] if contract else None, shape, scope)


def _shape_of(node) -> tuple[str, ...]:
    """The member names of a list or tuple literal of strings (anything else counts for nothing)."""
    return tuple(filter(None, (_constant(e) for e in getattr(node, "elts", ()))))


def _python_files(paths) -> list[Path]:
    files: list[Path] = []
    for entry in paths:
        path = Path(entry)
        files += sorted(path.rglob("*.py")) if path.is_dir() else [path]
    return files


def _requirements_in(file: Path) -> list[tuple[str, ObservedRequirement]]:
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    found = [(str(file), req) for req in _module_requirements(tree)]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            calls = [d for d in node.decorator_list if isinstance(d, ast.Call)]
            found += [(f"{file}::{node.name}", req) for req in map(_requirement, calls) if req is not None]
    return found


def _module_requirements(tree: ast.Module) -> list[ObservedRequirement]:
    """The requirements of a module-level `itf_requires = itf.requires(...)` (or a list of them)."""
    found = []
    for node in tree.body:
        targets = (
            node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        )
        if any(isinstance(t, ast.Name) and t.id == "itf_requires" for t in targets) and node.value is not None:
            calls = node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else [node.value]
            found += [req for req in (_requirement(c) for c in calls if isinstance(c, ast.Call)) if req is not None]
    return found


def collect_requirements(paths) -> list[tuple[str, ObservedRequirement]]:
    """`(test id, requirement)` for every `@itf.requires(...)` in the Python files under `paths`."""
    return [found for file in _python_files(paths) for found in _requirements_in(file)]


# ---- the inventory --------------------------------------------------------------------------------------------


def _definition(definition: Definition | None) -> dict | None:
    if definition is None:
        return None
    return {'version': definition.version, 'kind': definition.kind, 'summary': definition.summary, 'description': definition.description, 'role': definition.role, 'stability': definition.stability, 'replaced_by': definition.replaced_by, 'see_also': list(definition.see_also), 'probe': definition.probe, 'guarantees': list(definition.guarantees), 'members': [{'name': m.name, 'signature': m.signature, 'semantics': m.semantics, 'required': m.required} for m in definition.members], 'source': definition.source}




def _observes(factory) -> str:
    if not factory.observes:
        return "no"
    return "when its settings allow" if callable(factory.observes) else "yes"


def _factory(f) -> dict:
    return {
        "label": f.label,
        "pack": f.pack,
        "contract": f.contract,
        "major": f.major,
        "shape": sorted(m.name for m in f.gives.members),
        "needs": [
            {
                "slot": n.slot,
                "contract": n.contract,
                "expects": sorted(m.name for m in n.expected.members),
                "major": f.need_majors.get(n.slot),
            }
            for n in f.needs
        ],
        "config": f.config_schema.describe() if f.config_schema else [],
        "teardown": f.has_teardown,
        "observes": _observes(f),
    }


def _action(a) -> dict:
    return {
        "label": a.label,
        "pack": a.pack,
        "state": a.state,
        "also": sorted({*a.also, *a.extra_probes}),
        "after": list(a.after),
        "breaks": list(a.breaks),
        "probe": bool(a.probe),
        "uses": [
            {"slot": n.slot, "contract": n.contract, "expects": sorted(m.name for m in n.expected.members)}
            for n in a.uses
        ],
    }


def _contract_entry(name: str, entry) -> dict:
    data = entry.to_json()
    data['definition'] = _definition(entry.definition)
    return data


def _pack_entry(name: str, factories: list, actions: list) -> dict:
    return {
        **pack_info(name),
        "factories": [f["label"] for f in factories if f["pack"] == name],
        "actions": [a["label"] for a in actions if a["pack"] == name],
    }


def inventory(catalog, *, definitions=None, tests=(), errors=(), packs=None) -> dict:
    """Everything the map, the page and the reference show, as JSON-shaped data."""
    definitions = load_list() if definitions is None else list(definitions)
    contracts = contract_map(catalog, tests=[(i, r) for (i, r) in tests], definitions=definitions)
    names = list(packs) if packs is not None else list(catalog.packs())
    factories = [_factory(f) for f in sorted(catalog.factories.values(), key=lambda f: f.label)]
    actions = [_action(a) for a in sorted(catalog.action_descs.values(), key=lambda a: a.label)]
    return {'packs': [_pack_entry(name, factories, actions) for name in names], 'contracts': [_contract_entry(name, entry) for (name, entry) in contracts.items()], 'factories': factories, 'actions': actions, 'errors': list(errors)}
