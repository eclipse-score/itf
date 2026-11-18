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
"""Registration and origin assignment. Contributors meet only through names (see docs/concepts/architecture.rst)."""

from __future__ import annotations

import ast
import importlib
import inspect
from dataclasses import dataclass, field
from types import ModuleType

from .hooks import implements_itf_hooks, new_plugin_manager
from .publish import declared_expectations, declared_parts, label_of


class CrossContributorImport(Exception):
    """A contributor's globals hold a module, class or function owned by another contributor."""


class HookWrapperRejected(Exception):
    """A registered module implements a hookwrapper; hookwrappers are not allowed."""


# Decision: packs meet only through contract names. A contributor may not hold another contributor's
# classes or functions in its module globals (CrossContributorImport), so a pack cannot grow a hidden
# dependency on a sibling; it states what it needs as a token plus an expectation instead, and the planner
# wires whichever pack provides it. This is what makes two providers of one contract interchangeable.
#
# Packages whose direct children are separate contributors (`score.itf.packs.a`, `score.itf.packs.b`):
# under a shared namespace the top-level name cannot tell two packs apart.
NAMESPACE_PACKAGES = ("score.itf.packs",)
# Shared by every contributor and owned by none: the core and its public alias. Contracts are not
# shared code: a provider publishes its shape, a consumer declares what it expects.
CORE_PACKAGE = "score.itf.core"
# The contract definitions and their conformance checks are data about names, owned by no pack; a pack still
# may not import them (it declares its own expectations), only tools and the conformance entrypoint do.
CONTRACTS_PACKAGE = "score.itf.contracts"
SHARED_PACKAGES = (CORE_PACKAGE, CONTRACTS_PACKAGE)
# Core modules a contributor may import; anything else under `score.itf.core` is an internal.
PUBLIC_MODULES = frozenset({"score.itf", CORE_PACKAGE, f"{CORE_PACKAGE}.process"})


def _within(module_name: str, package: str) -> bool:
    return module_name == package or module_name.startswith(package + ".")


def _is_shared(module_name: str) -> bool:
    return module_name == "score.itf" or any(_within(module_name, p) for p in SHARED_PACKAGES)


def _top_level(module_name: str) -> str:
    """The contributor a module belongs to: its pack under a namespace package, else its top-level package."""
    for namespace in NAMESPACE_PACKAGES:
        if module_name.startswith(namespace + "."):
            depth = namespace.count(".") + 2
            return ".".join(module_name.split(".")[:depth])
    return module_name.split(".", 1)[0]


contributor_of = _top_level


def _load(module_or_name) -> ModuleType:
    if isinstance(module_or_name, ModuleType):
        return module_or_name
    return importlib.import_module(module_or_name)


def _check_no_hookwrappers(mod: ModuleType) -> None:
    for attr_name, val in vars(mod).items():
        opts = getattr(val, "itf_impl", None)
        if opts and (opts.get("hookwrapper") or opts.get("wrapper")):
            raise HookWrapperRejected(f"{mod.__name__}.{attr_name}: hookwrappers are not allowed on itf hooks")


def _suggest(attr_name: str, home: str, val) -> str:
    name = label_of(val)
    if name:
        return f"refer to it by its label in the target file instead: {name!r}"
    if isinstance(val, ModuleType):
        return f"list {home!r} in pytest_plugins instead of importing it"
    return f"refer to {attr_name!r} by name instead of importing {home!r}"


# Hookwrappers are rejected (_check_no_hookwrappers) because they run around other plugins' hooks and make
# the order of itf hooks observable to unrelated contributors; plain hookimpls keep each
# contributor's claims independent of registration order.
def _contributor_tops(modules: dict[str, ModuleType]) -> set[str]:
    return {_top_level(name) for name in modules if not _is_shared(name)}


def _core_public() -> frozenset[str]:
    from ... import core

    return frozenset(core.__all__)


def _refuse(mod_name: str, line: int, what: str, why: str, fix: str) -> None:
    raise CrossContributorImport(f"{mod_name}:{line} imports {what!r} \u2014 {why}; {fix}")


def _check_import_statements(mod_name: str, mod: ModuleType, contributor_tops: set[str]) -> None:
    try:
        tree = ast.parse(inspect.getsource(mod))
    except (OSError, TypeError, SyntaxError):
        return
    own_top = _top_level(mod_name)
    public = _core_public()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets = [(alias.name, None) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            targets = [(node.module, alias.name) for alias in node.names]
        else:
            continue
        for module, imported in targets:
            top = _top_level(module)
            if _is_shared(module) or (imported is not None and _is_shared(f"{module}.{imported}")):
                _check_shared_import(mod_name, node.lineno, module, imported, public)
            elif top != own_top and top in contributor_tops:
                _refuse(
                    mod_name,
                    node.lineno,
                    module if imported is None else f"{module}.{imported}",
                    f"{top!r} is another contributor",
                    "name its capabilities and actions by label in the target file; packs never import each other",
                )


def _check_shared_import(mod_name: str, line: int, module: str, imported: str | None, public: frozenset[str]) -> None:
    """The core is open to every contributor, but only through its public modules."""
    if imported is not None and f"{module}.{imported}" in PUBLIC_MODULES:
        return
    if module not in PUBLIC_MODULES:
        _refuse(
            mod_name,
            line,
            module,
            "ITF core internals are not a contributor API",
            f"import only from {', '.join(sorted(PUBLIC_MODULES))}",
        )
    if module in ("score.itf", CORE_PACKAGE) and imported not in (None, "*") and imported not in public:
        _refuse(
            mod_name,
            line,
            f"{module}.{imported}",
            "not part of ITF core's public API",
            f"public names are: {', '.join(sorted(public))}",
        )


def _check_cross_contributor_imports(modules: dict[str, ModuleType]) -> None:
    contributor_tops = _contributor_tops(modules)
    for mod_name, mod in modules.items():
        _check_import_statements(mod_name, mod, contributor_tops)
        own_top = _top_level(mod_name)
        for attr_name, val in vars(mod).items():
            if isinstance(val, ModuleType):
                home = val.__name__
            elif inspect.isclass(val) or inspect.isfunction(val):
                home = getattr(val, "__module__", None)
            else:
                continue
            if not home:
                continue
            home_top = _top_level(home)
            if _is_shared(home) or home_top == own_top:
                continue
            if home_top in contributor_tops:
                raise CrossContributorImport(
                    f"{mod_name} holds {attr_name!r} defined in {home!r} "
                    f"(package {home_top!r}, a different registered contributor); "
                    f"{_suggest(attr_name, home, val)}"
                )


# Lowest first: a target file outranks the packs it names (it may choose between two actions making one state true),
# and the project's policy outranks both.
ORIGINS = ("plugin", "target file", "policy")


@dataclass(frozen=True)
class Registry:
    pm: object
    modules: dict = field(default_factory=dict)  # module name -> module
    origins: dict = field(default_factory=dict)  # module name -> "plugin" | "target file" | "policy"

    def origin_of(self, module: ModuleType) -> str:
        return self.origins[module.__name__]

    def origin_of_package(self, top: str) -> str | None:
        found = {o for n, o in self.origins.items() if _top_level(n) == top}
        return max(found, key=ORIGINS.index) if found else None


def is_contributor(module: ModuleType) -> bool:
    """Implements an ITF hook, defines parts, or declares session API expectations."""
    return not _is_shared(module.__name__) and (
        implements_itf_hooks(module) or bool(declared_parts(module)) or bool(declared_expectations(module))
    )


def register_modules(entries) -> Registry:
    """`entries`: (module, origin) pairs. Checks that contributors share nothing but names and builds ITF's plugin manager."""
    pm = new_plugin_manager()
    modules: dict[str, ModuleType] = {}
    origins: dict[str, str] = {}
    for mod, origin in entries:
        name = mod.__name__
        if name in modules:
            origins[name] = max(origins[name], origin, key=ORIGINS.index)
            continue
        modules[name] = mod
        origins[name] = origin
    for name in sorted(modules):
        _check_no_hookwrappers(modules[name])
        pm.register(modules[name])
    _check_cross_contributor_imports(modules)
    return Registry(pm=pm, modules=modules, origins=origins)


def _plugin_names(module: ModuleType) -> list[str]:
    names = getattr(module, "pytest_plugins", ())
    return [names] if isinstance(names, str) else list(names)


def follow(items) -> list[tuple[ModuleType, str]]:
    """`items`: (module or module name, origin) pairs. Adds every module they name in `pytest_plugins`,
    as pytest would, at the origin `plugin`; a module is kept when it is a root or an ITF contributor."""
    entries: list[tuple[ModuleType, str]] = []
    seen: set[str] = set()
    frontier = [(_load(item), origin) for item, origin in items]
    while frontier:
        next_frontier = []
        for mod, origin in frontier:
            if mod.__name__ in seen:
                continue
            seen.add(mod.__name__)
            if origin == "policy" or is_contributor(mod):
                entries.append((mod, origin))
            next_frontier += [(_load(n), "plugin") for n in sorted(_plugin_names(mod))]
        frontier = next_frontier
    return entries


def expand(entries) -> list[tuple[ModuleType, str]]:
    """Without pytest: a (module, origin) pair is taken as it is; a bare module (or its name) is a pack
    entrypoint and brings the modules it lists in `pytest_plugins`, at the origin `plugin`."""
    found: list[tuple[ModuleType, str]] = []
    for entry in entries:
        found += [entry] if isinstance(entry, tuple) else follow([(entry, "plugin")])
    return found


def register(roots, extra=()) -> Registry:
    """Without pytest: `roots` are the project's policy; their `pytest_plugins` are followed as pytest would."""
    return register_modules([*follow((r, "policy") for r in roots), *extra])
