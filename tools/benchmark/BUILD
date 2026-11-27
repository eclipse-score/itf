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
load("@rules_python//python:defs.bzl", "py_binary", "py_library")

# Planning benchmark: `bazel run //tools/benchmark:plan_bench -- [TARGET_FILE...] [--scale ...] [--report FILE]`.
# Every ITF pack is on the path, so any target file made of ITF's packs can be measured. See README.md.

PACKS = [
    "//score/itf/packs/core_dump",
    "//score/itf/packs/dlt",
    "//score/itf/packs/docker",
    "//score/itf/packs/localhost",
    "//score/itf/packs/net",
    "//score/itf/packs/pcap",
    "//score/itf/packs/ping",
    "//score/itf/packs/qemu",
    "//score/itf/packs/serial",
    "//score/itf/packs/ssh",
]

py_library(
    name = "lib",
    srcs = ["plan_bench.py"],
    visibility = ["//test:__subpackages__"],
    deps = ["//score/itf/core"] + PACKS,
)

py_binary(
    name = "plan_bench",
    srcs = ["plan_bench.py"],
    main = "plan_bench.py",
    deps = [":lib"],
)
