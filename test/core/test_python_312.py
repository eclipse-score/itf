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
"""Verify ITF modules and syntax using the supported Python 3.12 toolchain."""

import importlib
import sys

import pytest

ITF_MODULES = [
    "score.itf",
    "score.itf.core.process.console",
    "score.itf.core.frontends.target_file",
    "score.itf.packs.dlt.plugin",
    "score.itf.packs.docker.plugin",
    "score.itf.packs.localhost.plugin",
    "score.itf.packs.qemu.plugin",
]


def test_interpreter_is_python_3_12():
    assert sys.version_info[:2] == (3, 12), f"expected Python 3.12, got {sys.version.split()[0]}"


@pytest.mark.parametrize("module_name", ITF_MODULES)
def test_itf_module_imports(module_name):
    importlib.import_module(module_name)


def test_type_statement_is_supported():
    namespace = {}
    exec("type IntList = list[int]", namespace)
    assert namespace["IntList"].__value__ == list[int]
