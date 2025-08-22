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

def py_itf_test(name, srcs, args = [], data = [], plugins = [], **kwargs):
    pytest_bootstrap = Label("@score_itf//:main.py")
    pytest_ini = Label("@score_itf//:pytest.ini")

    plugins = ["-p %s" % plugin for plugin in plugins]

    py_test(
        name = name,
        srcs = [
            pytest_bootstrap,
        ] + srcs,
        main = pytest_bootstrap,
        args = args +
               ["-c $(location %s)" % pytest_ini] +
               [
                   "-p no:cacheprovider",
                   "--show-capture=no",
               ] +
               plugins +
               ["$(location %s)" % x for x in srcs],
        deps = [
            requirement("docker"),
            requirement("pytest"),
            requirement("paramiko"),
            requirement("typing-extensions"),
            "@score_itf//:itf",
        ],
        data = [
            pytest_ini,
        ] + data,
        env = {
            "PYTHONDONOTWRITEBYTECODE": "1",
        },
        **kwargs
    )
