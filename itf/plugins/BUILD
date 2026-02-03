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
load("@itf_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_library")

py_library(
    name = "core",
    srcs = ["core.py"],
    visibility = ["//visibility:public"],
    deps = [
        requirement("pytest"),
    ],
)

py_library(
    name = "docker",
    srcs = ["docker.py"],
    visibility = ["//visibility:public"],
    deps = [
        requirement("docker"),
        requirement("pytest"),
    ],
)
