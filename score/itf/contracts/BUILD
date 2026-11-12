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
load("@itf_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_library")
load("//bazel:py_itf_plugin.bzl", "py_itf_plugin")

filegroup(
    name = "definitions",
    srcs = glob(["definitions/*.yaml"]),
    visibility = ["//visibility:public"],
)

# Contract definitions (YAML) and the runner-agnostic checks that hold providers to them. A shared
# package: data and checks only, no pack imports. `pytest_conformance` is the pytest entrypoint
# (//score/itf/contracts:conformance is the plugin to put in py_itf_test(plugins = ...)).
py_library(
    name = "contracts",
    srcs = glob(
        ["**/*.py"],
        exclude = ["pytest_conformance.py"],
    ),
    data = [":definitions"],
    visibility = ["//visibility:public"],
    deps = [
        "//score/itf/core",
        requirement("pyyaml"),
    ],
)

py_library(
    name = "pytest_conformance_lib",
    srcs = ["pytest_conformance.py"],
    visibility = ["//visibility:private"],
    deps = [
        ":contracts",
        "//score/itf/core",
        requirement("pytest"),
    ],
)

py_itf_plugin(
    name = "conformance",
    enabled_plugins = ["score.itf.contracts.pytest_conformance"],
    py_library = ":pytest_conformance_lib",
    visibility = ["//visibility:public"],
)
