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
load("//:defs.bzl", "py_itf_test")

# Plain pytest plugins work with py_itf_test as before: no target file, no ITF target.
py_itf_test(
    name = "test_attribute_plugin",
    srcs = ["test_attribute_plugin.py"],
    args = [
        "-p",
        "pytester",
    ],
    plugins = ["//:attribute_plugin"],
)
