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
load("@rules_python//python:defs.bzl", "py_library")
load("@score_itf//:defs.bzl", "itf_target", "py_itf_test")
load("@score_itf//bazel:py_itf_plugin.bzl", "py_itf_plugin")

# A Raspberry Pi on a hardware bench, as an illustration (see README.md). bench_pack/bench sketches a power
# supply, an SD-card flasher and the board as `platform`, with the members tests rely on and no instrument code.
# Ping, SSH with a key, SFTP and DLT come from ITF's packs.
#
# `bazel build //examples/rpi_bench:all` compiles both target files without a bench (unset values are fine
# there; a run reads them from the environment or targets/.env): the roles, the wiring and
# the ordered actions (flash, start DLT, power on, open SSH) in target_rpi.plan.json. The tests are manual: they
# need the bench.

py_library(
    name = "bench_lib",
    srcs = glob(["bench_pack/bench/**/*.py"]),
    data = glob(["bench_pack/bench/**/*.yaml"]),
    imports = ["bench_pack"],
    deps = ["@score_itf//:itf"],
)

py_itf_plugin(
    name = "bench",
    enabled_plugins = ["bench.plugin"],
    pack = "bench",
    py_library = ":bench_lib",
)

PACKS = [
    ":bench",
    "@score_itf//score/itf/packs/dlt",
    "@score_itf//score/itf/packs/net",
    "@score_itf//score/itf/packs/ping",
    "@score_itf//score/itf/packs/ssh",
]

itf_target(
    name = "target_rpi",
    src = "targets/rpi.itf.yaml",
    data = glob(
        ["targets/.env"],  # the bench's values (see targets/.env.example); git ignores it
        allow_empty = True,
    ),
    packs = PACKS,
)

py_itf_test(
    name = "rpi",
    srcs = ["test_rpi.py"],
    tags = [
        "external",
        "manual",
    ],
    target = ":target_rpi",
)

# The same board with a card flashed by hand: image.flashed is assumed, the flasher never built.
itf_target(
    name = "target_rpi_preflashed",
    src = "targets/rpi.itf.yaml",
    data = glob(
        ["targets/.env"],  # the bench's values (see targets/.env.example); git ignores it
        allow_empty = True,
    ),
    overrides = ["targets/preflashed.itf.yaml"],
    packs = PACKS,
)

py_itf_test(
    name = "rpi_preflashed",
    srcs = ["test_rpi.py"],
    tags = [
        "external",
        "manual",
    ],
    target = ":target_rpi_preflashed",
)
