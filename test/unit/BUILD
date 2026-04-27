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
load("//:defs.bzl", "py_itf_unittest")

py_itf_unittest(
    name = "test_ping",
    srcs = ["test_ping.py"],
)

py_itf_unittest(
    name = "test_qemu_config_schema",
    srcs = ["test_qemu_config_schema.py"],
    deps = ["//score/itf/plugins/qemu:config"],
)

test_suite(
    name = "unit",
    tests = [
        ":test_ping",
        ":test_qemu_config_schema",
    ],
)
