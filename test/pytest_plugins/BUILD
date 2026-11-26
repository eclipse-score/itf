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

itf_target(
    name = "target_pack_imports",
    src = "target_pack_imports.itf.yaml",
    packs = [
        "//score/itf/packs/localhost",
        "//score/itf/packs/sim",
    ],
)

py_itf_test(
    name = "test_target_pack_imports",
    srcs = ["test_target_pack_imports.py"],
    target = ":target_pack_imports",
)
