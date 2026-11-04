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
"""What a pack may import. Packs never import each other (they meet through contract names, their consumers
declare their own Protocols), and a pack that contributes capabilities and actions never imports pytest; only a
pytest plugin module of a pack (`pytest_plugin.py`) may."""

import ast
from pathlib import Path

import yaml

PACKS = Path(__file__).absolute().parents[3] / "score" / "itf" / "packs"


def _imports(path: Path) -> list[tuple[int, str]]:
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found += [(node.lineno, node.module)]
    return found


def _packs() -> list[Path]:
    return sorted(p for p in PACKS.iterdir() if (p / "pack.yaml").is_file())


def test_every_pack_has_a_name_that_is_its_directory():
    for pack in _packs():
        assert yaml.safe_load((pack / "pack.yaml").read_text(encoding="utf-8"))["name"] == pack.name


def test_packs_never_import_each_other():
    offenders = []
    for pack in _packs():
        for path in pack.rglob("*.py"):
            for line, module in _imports(path):
                parts = module.split(".")
                if parts[:3] == ["score", "itf", "packs"] and len(parts) > 3 and parts[3] != pack.name:
                    offenders.append(f"{path.relative_to(PACKS)}:{line} imports {module}")
    assert not offenders, offenders


def test_capability_packs_never_import_pytest():
    offenders = []
    for pack in _packs():
        for path in pack.rglob("*.py"):
            if path.name == "pytest_plugin.py":
                continue
            for line, module in _imports(path):
                if module.split(".")[0] == "pytest":
                    offenders.append(f"{path.relative_to(PACKS)}:{line} imports {module}")
    assert not offenders, offenders


def test_a_pack_has_a_plugin_module_the_label_loader_can_find():
    for pack in _packs():
        if pack.name != "core_dump" or (pack / "plugin.py").is_file():
            assert (pack / "plugin.py").is_file(), f"{pack.name} has no plugin.py"
