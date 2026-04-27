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

"""Lightweight macro for running unit tests via pytest without ITF plugin infrastructure."""

load("@rules_python//python:defs.bzl", "py_test")

def py_itf_unittest(name, srcs, deps = [], data = [], env = {}, pytest_config = None, **kwargs):
    """Thin py_test wrapper for unit tests that do not need ITF plugin machinery.

    Unlike py_itf_test, this macro creates a direct py_test with no launcher
    script or plugin infrastructure, so Bazel coverage works out of the box.

    Args:
        name: Target name.
        srcs: Python test source files.
        deps: Additional Python dependencies.
        data: Data files available at runtime.
        env: Environment variables for the test.
        pytest_config: Optional pytest config file. Defaults to @score_itf//:pytest.ini.
        **kwargs: Forwarded to py_test (e.g. size, timeout, tags).
    """
    pytest_bootstrap = Label("@score_itf//:main.py")
    if not pytest_config:
        pytest_config = Label("@score_itf//:pytest.ini")

    py_test(
        name = name,
        srcs = [pytest_bootstrap] + srcs,
        main = pytest_bootstrap,
        args = [
            "-c $(location %s)" % pytest_config,
            "-p no:cacheprovider",
            "--show-capture=no",
            "--junitxml=$$XML_OUTPUT_FILE",
        ] + ["$(location %s)" % x for x in srcs],
        deps = ["@score_itf//:itf", "@itf_pip//pytest_mock"] + deps,
        data = [pytest_config] + data,
        env = {"PYTHONDONOTWRITEBYTECODE": "1"} | env,
        **kwargs
    )
