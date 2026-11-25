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
"""Text file I/O names its encoding: Windows defaults to cp1252, which cannot write e.g. `→`."""

import ast
import os
from pathlib import Path

ROOT = Path(__file__).absolute().parents[3]
SOURCES = [ROOT / "score" / "itf" / "core", ROOT / "score" / "itf" / "packs"]


def _mode(call: ast.Call) -> str:
    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant):
        return str(call.args[1].value)
    for keyword in call.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
            return str(keyword.value.value)
    return "r"


def _implicit_encoding(call: ast.Call) -> bool:
    if any(keyword.arg == "encoding" for keyword in call.keywords):
        return False
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    if name in ("read_text", "write_text"):
        return True
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "tarfile":
        return False  # tar archives are bytes, whatever the mode string says
    # open(path, ...) and path.open(...): only text mode decodes; binary modes have no encoding
    return name == "open" and bool(call.args or call.keywords) and "b" not in _mode(call)


def test_text_file_io_names_its_encoding():
    offenders = []
    for root in SOURCES:
        for directory, subdirs, files in os.walk(root):
            subdirs[:] = [
                name
                for name in subdirs
                if name not in ("tests", "__pycache__") and not (Path(directory) / name / "pyvenv.cfg").is_file()
            ]
            for name in files:
                if not name.endswith(".py"):
                    continue
                source = Path(directory) / name
                for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
                    if isinstance(node, ast.Call) and _implicit_encoding(node):
                        offenders.append(f"{source.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, "pass encoding='utf-8' to: " + ", ".join(offenders)
