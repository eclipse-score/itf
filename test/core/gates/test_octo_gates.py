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
"""AST-walk score.itf.core/octo/*.py: imports are stdlib or relative; no banned word appears
in source, docstrings, string literals or test names."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).absolute().parents[3]
OCTO_DIR = ROOT / "score" / "itf" / "core" / "octo"
OCTO_TESTS_DIR = ROOT / "test" / "core" / "octo"
WORDLIST_PATH = ROOT / "tools" / "gates" / "octo_banned_words.txt"

STDLIB = set(sys.stdlib_module_names)


def _octo_py_files():
    return sorted(OCTO_DIR.rglob("*.py"))


def test_octo_imports_only_stdlib_or_relative():
    for path in _octo_py_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top in STDLIB, f"{path}: non-stdlib absolute import {alias.name!r}"
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue  # relative import: fine
                top = (node.module or "").split(".")[0]
                assert top in STDLIB, f"{path}: non-stdlib absolute import {node.module!r}"


def test_the_core_knows_no_kind():
    """Core modules never import the standard kinds; only the package `__init__` assembles them,
    so capability and state are registered exactly the way a third kind would be."""
    for path in sorted(OCTO_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                assert not (node.module or "").startswith("std"), f"{path}: imports the standard kinds"
                assert node.module or not any(a.name == "std" for a in node.names), f"{path}: imports std"


def _banned_words() -> list[str]:
    return [w.strip() for w in WORDLIST_PATH.read_text().splitlines() if w.strip()]


def _find_banned(text: str, words: list[str]) -> list[str]:
    hits = []
    for w in words:
        if re.search(rf"\b{re.escape(w)}\b", text, re.IGNORECASE):
            hits.append(w)
    return hits


def test_octo_source_has_no_banned_words():
    words = _banned_words()
    offenders = {}
    for path in _octo_py_files():
        hits = _find_banned(path.read_text(), words)
        if hits:
            offenders[str(path)] = hits
    assert not offenders, f"banned words found: {offenders}"


def test_octo_test_names_have_no_banned_words():
    words = _banned_words()
    offenders = {}
    for path in sorted(OCTO_TESTS_DIR.rglob("test_*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                hits = _find_banned(node.name, words)
                if hits:
                    offenders[f"{path}:{node.name}"] = hits
    assert not offenders, f"banned words in test names: {offenders}"
