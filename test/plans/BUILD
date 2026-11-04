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
load("@rules_python//python:defs.bzl", "py_binary")
load("//:defs.bzl", "itf_target", "py_itf_unittest")

PACKS = ["//score/itf/packs/sim"]

# A target file compiled during the build: bazel build //test/plans:ok writes ok.plan.json.
itf_target(
    name = "ok",
    src = "ok.itf.yaml",
    packs = PACKS,
)

# The same planner an itf_target uses, run by hand on target files that must fail the build.
py_binary(
    name = "failing_planner",
    srcs = ["//bazel:itf_plan.py"],
    main = "//bazel:itf_plan.py",
    deps = [
        "//:itf",
        "//score/itf/packs/localhost",
    ] + PACKS,
)

py_itf_unittest(
    name = "plan_test",
    srcs = ["test_plan.py"],
    data = [
        "no_store.itf.yaml",
        "pack_outside.itf.yaml",
        "unset_value.itf.yaml",
        ":failing_planner",
        ":ok",
    ],
    env = {
        "NO_STORE": "$(rootpath no_store.itf.yaml)",
        "OK_PLAN": "$(rootpath :ok)",
        "OUTSIDE": "$(rootpath pack_outside.itf.yaml)",
        "PLANNER": "$(rootpath :failing_planner)",
        "UNSET": "$(rootpath unset_value.itf.yaml)",
    },
)

# Every target file the repository ships, compiled the way an itf_target compiles it, but without building the
# files it names: the QEMU target files are manual (their images are large downloads), so no build compiles them.
ALL_PACKS = ["//score/itf/packs/" + pack for pack in [
    "core_dump",
    "dlt",
    "docker",
    "localhost",
    "net",
    "pcap",
    "ping",
    "qemu",
    "serial",
    "sim",
    "ssh",
]]

py_binary(
    name = "planner",
    srcs = ["//bazel:itf_plan.py"],
    main = "//bazel:itf_plan.py",
    deps = ["//:itf"] + ALL_PACKS,
)

py_itf_unittest(
    name = "shipped_targets_test",
    srcs = ["test_shipped_targets.py"],
    data = [
        ":planner",
        "//score/itf/compat:target_files",
        "//test/integration:target_files",
    ],
    env = {"PLANNER": "$(rootpath :planner)"},
)
