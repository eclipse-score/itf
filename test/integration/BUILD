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
load("//:defs.bzl", "itf_target", "py_itf_test")

SUITE = glob(["suite/*.py"])

OBSERVABILITY_SUITE = [
    "suite/test_command.py",
    "suite/test_console.py",
]

PCAP_SUITE = ["suite/test_capture.py"]

# ---- the test host: runs anywhere, no daemon

itf_target(
    name = "target_localhost",
    src = "targets/localhost.itf.yaml",
    srcs = ["targets/policy.py"],
    data = glob(["targets/**/*.itf.yaml"]),
    packs = ["//score/itf/packs/localhost"],
)

py_itf_test(
    name = "localhost",
    timeout = "long",
    srcs = ["conftest.py"] + SUITE,
    target = ":target_localhost",
    target_compatible_with = ["@platforms//os:linux"],
)

# The same host with an override file: the facts of one setup (the platform's working directory).
itf_target(
    name = "target_localhost_override",
    src = "targets/localhost.itf.yaml",
    srcs = ["targets/policy.py"],
    data = glob(["targets/**/*.itf.yaml"]),
    overrides = ["overrides/localhost.itf.yaml"],
    packs = ["//score/itf/packs/localhost"],
)

py_itf_test(
    name = "localhost_override",
    timeout = "long",
    srcs = ["conftest.py"] + SUITE + [
        "specific/test_override_values.py",
    ],
    target = ":target_localhost_override",
    target_compatible_with = ["@platforms//os:linux"],
)
