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

# The optional contract library: definitions from the packs, the map, skeletons and contract rules.
py_itf_unittest(
    name = "contracts_test",
    srcs = glob(["test_*.py"]) + glob(["fixtures/*.py"]),
    deps = [
        "//score/itf/contracts",
        "//score/itf/core",
        "//score/itf/packs/dlt",
        "//score/itf/packs/localhost",
        "//score/itf/packs/net",
        "//score/itf/packs/ping",
    ],
)
