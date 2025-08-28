# *******************************************************************************
# Copyright (c) 2025 Contributors to the Eclipse Foundation
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

py_library(
    name = "base",
    srcs = [
        "__init__.py",
        "base_plugin.py",
        "constants.py",
    ],
    imports = ["."],
    visibility = ["//visibility:public"],
    deps = [
        "//itf/plugins/base/os",
        "//itf/plugins/base/target",
        "//itf/plugins/base/test",
        "//itf/plugins/utils",
    ],
)
