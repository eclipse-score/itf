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

# The planner: pure standard library. deps must stay empty (DR-002: it plans from declarations only).
py_library(
    name = "octo",
    srcs = glob(["**/*.py"]),
    visibility = ["//visibility:public"],
    deps = [],
)

exports_files(["README.md"])
