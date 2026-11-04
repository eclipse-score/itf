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

py_library(
    name = "lib",
    srcs = glob(["**/*.py"]) + ["//score/itf/packs:init"],
    data = [
        "README.md",
        "pack.yaml",
        "//score/itf/contracts:definitions",
    ] + glob(["contracts/*.yaml"]),
    visibility = ["//test/packs:__subpackages__"],
    deps = [
        "//score/itf/core",
        "//score/itf/core/process",
        requirement("docker"),
    ],
)

py_itf_plugin(
    name = "docker",
    enabled_plugins = ["score.itf.packs.docker.plugin"],
    pack = "docker",
    py_library = ":lib",
    visibility = ["//visibility:public"],
)

# For tools and gates that read the pack's metadata and sources from runfiles.
exports_files(
    ["pack.yaml"],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "sources",
    srcs = ["pack.yaml"] + glob(["**/*.py"]),
    visibility = ["//test/core:__pkg__"],
)
