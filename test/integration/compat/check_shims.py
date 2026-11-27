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
"""The original module paths hold no logic: every module of score.itf.plugins, score.itf.core.com,
score.itf.core.target and score.itf.core.utils only re-exports names (from score.itf.compat or a pack). The
whole compatibility layer is therefore score.itf.compat, and removing it is deleting it and these shims."""

import ast
import importlib
from pathlib import Path

import pytest

PACKAGES = ("score.itf.plugins", "score.itf.core.com", "score.itf.core.target", "score.itf.core.utils")


def shim_files() -> list[Path]:
    files = []
    for package in PACKAGES:
        root = Path(importlib.import_module(package).__file__).parent
        files += sorted(root.rglob("*.py"))
    return files


@pytest.mark.parametrize("path", shim_files(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_a_shim_only_re_exports(path):
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # the docstring
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("score.itf."):
            continue
        pytest.fail(f"{path}: line {node.lineno} is more than a re-export ({type(node).__name__})")


def test_there_are_shims_to_check():
    assert len(shim_files()) >= 10
