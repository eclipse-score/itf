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
"""Pack loading from factory labels. The pack `<name>` is, in this order: the module a target file names for it
(`packs: <name>: <module>`), the module `score.itf.packs.<name>.plugin`, the entry point
`score_itf.packs:<name>`; else an error saying what is known."""

from __future__ import annotations

import importlib
import importlib.util
from importlib import metadata
from types import ModuleType

ENTRY_POINT_GROUP = "score_itf.packs"
PACKS_PACKAGE = "score.itf.packs"


class PackNotFound(ValueError):
    pass


def pack_of(label: str) -> str:
    """`acme.exec` -> `acme`."""
    return label.split(".", 1)[0]


def _entry_points() -> dict:
    try:
        return {ep.name: ep for ep in metadata.entry_points(group=ENTRY_POINT_GROUP)}
    except Exception:  # noqa: BLE001
        return {}


def known() -> tuple[str, ...]:
    names = set(_entry_points())
    try:
        package = importlib.import_module(PACKS_PACKAGE)
        for path in getattr(package, "__path__", ()):
            from pathlib import Path

            names |= {p.name for p in Path(path).iterdir() if (p / "plugin.py").is_file()}
    except ImportError:
        pass
    return tuple(sorted(names))


def load(name: str, modules=None) -> ModuleType:
    if modules and name in modules:
        return importlib.import_module(modules[name])
    module = f"{PACKS_PACKAGE}.{name}.plugin"
    try:
        found = importlib.util.find_spec(module)
    except (ImportError, ValueError):
        found = None
    if found is not None:
        return importlib.import_module(module)
    entry = _entry_points().get(name)
    if entry is not None:
        loaded = entry.load()
        return loaded if isinstance(loaded, ModuleType) else importlib.import_module(entry.value.split(":")[0])
    raise PackNotFound(
        f"pack {name!r} is neither the module {module} nor an entry point of group {ENTRY_POINT_GROUP!r}, and the "
        f"target file does not say where it lives (packs: {name}: <module>); "
        f"known packs: {', '.join(known()) or '(none)'}"
    )
