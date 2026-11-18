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
    name = "cli_test",
    srcs = ["conftest.py"] + glob([
        "test_*.py",
        "fixtures/*.py",
    ]),
    data = glob(["definitions/*.yaml"]),
    deps = [
        "//score/itf/cli",
        "//score/itf/contracts",
        "//score/itf/packs/localhost",
        "//score/itf/packs/sim",
    ],
)
