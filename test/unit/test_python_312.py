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

# Verifies that the ITF unit tests run on the Python 3.12 toolchain and that the
# score.itf modules import and behave correctly under it.

import importlib
import sys

import pytest

ITF_MODULES = [
    "score.itf",
    "score.itf.core.com.ping",
    "score.itf.core.process.console",
    "score.itf.core.utils.bazel",
    "score.itf.plugins.core",
    "score.itf.plugins.dlt",
    "score.itf.plugins.docker",
    "score.itf.plugins.qemu",
]


def test_interpreter_is_python_3_12():
    assert sys.version_info[:2] == (3, 12), f"expected Python 3.12, got {sys.version.split()[0]}"


@pytest.mark.parametrize("module_name", ITF_MODULES)
def test_itf_module_imports(module_name):
    importlib.import_module(module_name)


def test_type_statement_is_supported():
    # PEP 695 `type` aliases are 3.12+ syntax. Compiling them proves the
    # toolchain really is 3.12, not just a version string.
    namespace = {}
    exec("type IntList = list[int]", namespace)
    assert namespace["IntList"].__value__ == list[int]
