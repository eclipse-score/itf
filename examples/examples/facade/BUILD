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
load("@score_itf//:defs.bzl", "itf_target", "py_itf_test")

# Tutorial: adopting ITF without rewriting tests (README.md). The project's own target API is a facade in
# conftest.py; test_ecu.py calls target.run/push/pull, unchanged, on the host and in a container. Step 1 is the
# target files below, one per machine; nothing here uses the compatibility layer.

itf_target(
    name = "target_host",
    src = "targets/host/host.itf.yaml",
    packs = ["@score_itf//score/itf/packs/localhost"],
)

py_itf_test(
    name = "test_host",
    srcs = [
        "conftest.py",
        "test_ecu.py",
    ],
    target = ":target_host",
    target_compatible_with = ["@platforms//os:linux"],
)

itf_target(
    name = "target_container",
    src = "targets/container/container.itf.yaml",
    packs = ["@score_itf//score/itf/packs/docker"],
)

py_itf_test(
    name = "test_container",
    srcs = [
        "conftest.py",
        "test_ecu.py",
    ],
    target = ":target_container",
    target_compatible_with = ["@platforms//os:linux"],
)
