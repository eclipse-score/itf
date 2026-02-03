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
load("@rules_python//python:defs.bzl", "py_library")
load("@rules_python//python:pip.bzl", "compile_pip_requirements")
load("@score_tooling//:defs.bzl", "copyright_checker")

compile_pip_requirements(
    name = "requirements",
    src = "requirements.in",
    requirements_txt = "requirements_lock.txt",
)

exports_files([
    "main.py",
    "pytest.ini",
])

py_library(
    name = "itf",
    srcs = [
        "itf/__init__.py",
    ],
    data = [
        "//config",
    ],
    imports = ["."],
    visibility = ["//visibility:public"],
    deps = [
        "//itf/plugins:core",
    ],
)

test_suite(
    name = "format.check",
    tests = ["//tools/format:format.check"],
)

alias(
    name = "format.fix",
    actual = "//tools/format:format.fix",
)

exports_files([
    ".ruff.toml",
])

copyright_checker(
    name = "copyright",
    srcs = [
        ".github",
        "bazel",
        "deps",
        "examples",
        "itf",
        "scripts",
        "test",
        "tools",
        "//:BUILD",
        "//:MODULE.bazel",
        "//:main.py",
    ],
    config = "@score_tooling//cr_checker/resources:config",
    template = "@score_tooling//cr_checker/resources:templates",
    visibility = ["//visibility:public"],
)
