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

# tcpdump and libpcap built from source, shipped beside the pack and found through runfiles.
copy_file(
    name = "tcpdump_bin",
    src = "@tcpdump",
    out = "tcpdump",
    allow_symlink = True,
    is_executable = True,
    visibility = ["//test/integration:__pkg__"],
)

py_library(
    name = "lib",
    srcs = glob(["**/*.py"]) + ["//score/itf/packs:init"],
    data = [
        "README.md",
        "pack.yaml",
        ":tcpdump_bin",
        "//score/itf/contracts:definitions",
    ] + glob(["contracts/*.yaml"]),
    visibility = ["//test/packs:__subpackages__"],
    deps = [
        "//score/itf/core",
        "@rules_python//python/runfiles",
    ],
)

# Capture on a platform's interface, started after itf.states.platform.up.
py_itf_plugin(
    name = "pcap",
    enabled_plugins = ["score.itf.packs.pcap.plugin"],
    pack = "pcap",
    py_library = ":lib",
    visibility = ["//visibility:public"],
)

# Capture on a host interface, started first (records a whole boot).
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
