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

# The original qemu plugin's labels; the modules re-export from score.itf.compat and the qemu pack.
py_library(
    name = "config",
    srcs = ["config.py"],
    visibility = ["//visibility:public"],
    deps = ["//score/itf/compat"],
)

py_library(
    name = "qemu",
    srcs = [
        "__init__.py",
        "image_format.py",
        "qemu.py",
        "qemu_target.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":config",
        "//score/itf/plugins:core",
    ],
)
