# *******************************************************************************
# Copyright (c) 2025 Contributors to the Eclipse Foundation
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
"""Bazel interface for running pytest"""

load("@itf_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_test")
load("@score_itf//bazel/rules:run_as_exec.bzl", "test_as_exec")

def py_itf_test(name, srcs, args = [], data = [], plugins = [], **kwargs):
    """Bazel macro for running ITF tests.

    Args:
      name: Name of the test target.
      srcs: List of source files for the test.
      args: Additional arguments to pass to ITF.
      data: Data files needed for the test.
      plugins: List of pytest plugins to enable.
      **kwargs: Additional keyword arguments passed to py_test.
    """
    pytest_bootstrap = Label("@score_itf//:main.py")
    pytest_ini = Label("@score_itf//:pytest.ini")

    plugins = ["-p %s" % plugin for plugin in plugins]

    py_test(
        name = "_" + name,
        srcs = [
            pytest_bootstrap,
        ] + srcs,
        main = pytest_bootstrap,
        deps = [
            requirement("docker"),
            requirement("pytest"),
            requirement("paramiko"),
            requirement("typing-extensions"),
            requirement("netifaces"),
            "@score_itf//:itf",
        ],
        tags = ["manual"],
    )

    test_as_exec(
        name = name,
        executable = "_" + name,
        data_as_exec = [pytest_ini] + srcs,
        data = data,
        args = args +
               ["-c $(location %s)" % pytest_ini] +
               [
                   "-p no:cacheprovider",
                   "--show-capture=no",
               ] +
               plugins +
               ["$(location %s)" % x for x in srcs],
        env = {
            "PYTHONDONOTWRITEBYTECODE": "1",
        },
        **kwargs
    )
