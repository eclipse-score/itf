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
"""Every host process is started through ProcessWrapper, so ITF can track it and promise it is stopped."""

import ast
import os
from pathlib import Path

ROOT = Path(__file__).absolute().parents[3]
SOURCES = [ROOT / "score" / "itf" / "core", ROOT / "score" / "itf" / "packs"]
ALLOWED = ROOT / "score" / "itf" / "core" / "process" / "process_wrapper.py"
SPAWNERS = (
    {("subprocess", name) for name in ("Popen", "run", "call", "check_call", "check_output", "getoutput")}
    | {("os", name) for name in ("system", "popen", "fork", "forkpty", "execv", "execvp", "spawnv", "posix_spawn")}
    | {
        ("pty", "fork"),
        ("asyncio", "create_subprocess_exec"),
        ("asyncio", "create_subprocess_shell"),
    }
)


def _spawns(call: ast.Call) -> bool:
    func = call.func
    return (
        isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and (func.value.id, func.attr) in SPAWNERS
    )


def test_no_source_starts_a_process_except_the_wrapper():
    offenders = []
    for root in SOURCES:
        for directory, subdirs, files in os.walk(root):
            subdirs[:] = [name for name in subdirs if name != "__pycache__"]
            for name in files:
                source = Path(directory) / name
                if not name.endswith(".py") or source == ALLOWED:
                    continue
                for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
                    if isinstance(node, ast.Call) and _spawns(node):
                        offenders.append(f"{source.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, "start processes with ProcessWrapper (or ProcessWrapper.run): " + ", ".join(offenders)
