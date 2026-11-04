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

# A vendor's contract, end to end (see README.md). acme_pack/ is what Acme's distribution contains once
# installed (a site-packages directory):
#   acme/            the pack: a factory fulfilling `acme/power.relay`, the definition (contracts/power.yaml)
# Nothing registers the contract anywhere: its name is the vendor's own.

py_library(
    name = "acme_lib",
    srcs = glob(["acme_pack/acme/**/*.py"]),
    data = glob(["acme_pack/acme/**/*.yaml"]),
    imports = ["acme_pack"],
    deps = ["@score_itf//score/itf/contracts"],
)

py_itf_plugin(
    name = "acme",
    enabled_plugins = ["acme.plugin"],
    pack = "acme",
    py_library = ":acme_lib",
)

itf_target(
    name = "target",
    src = "targets/target.itf.yaml",
    srcs = ["targets/policy.py"],
    packs = [":acme"],
)

py_itf_test(
    name = "test",
    srcs = ["test_relay.py"],
    target = ":target",
)

