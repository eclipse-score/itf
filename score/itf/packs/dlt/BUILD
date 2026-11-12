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
load("@bazel_skylib//rules:copy_file.bzl", "copy_file")
load("@rules_python//python:defs.bzl", "py_library")
load("//bazel:py_itf_plugin.bzl", "py_itf_plugin")

# Built from source (third_party/dlt) and shipped beside the pack, found through runfiles.
copy_file(
    name = "libdlt",
    src = "//third_party/dlt:libdlt.so",
    out = "libdlt.so.2",
    allow_symlink = True,
)

copy_file(
    name = "dlt_receive_bin",
    src = "//third_party/dlt:dlt-receive",
    out = "dlt-receive",
    allow_symlink = True,
    is_executable = True,
)

py_library(
    name = "lib",
    srcs = glob(["**/*.py"]) + ["//score/itf/packs:init"],
    data = [
        "README.md",
        "pack.yaml",
        ":dlt_receive_bin",
        ":libdlt",
        "//score/itf/contracts:definitions",
    ] + glob(["contracts/*.yaml"]),
    visibility = [
        "//score/itf/plugins/dlt:__pkg__",
        "//test/packs:__subpackages__",
    ],
    deps = [
        "//score/itf/contracts",
        "//score/itf/core",
        "//score/itf/core/process",
        "//third_party/python_dlt",
        "@rules_python//python/runfiles",
    ],
)

py_itf_plugin(
    name = "dlt",
    enabled_plugins = ["score.itf.packs.dlt.plugin"],
    pack = "dlt",
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
