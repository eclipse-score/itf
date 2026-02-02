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
load("//bazel/rules:build_as_host.bzl", "as_host")
load("@rules_python//python:defs.bzl", "py_library")

as_host(
    name = "dlt-receive_as_host",
    src = "@dlt_daemon//:dlt-receive",
    visibility = ["//visibility:public"],
)

as_host(
    name = "libdlt_as_host.so",
    src = "@dlt_daemon//:libdlt.so",
    visibility = ["//visibility:public"],
)

genrule(
    name = "dlt-artifacts",
    outs = [
        "dlt-receive",
        "libdlt.so",
    ],
    cmd = """
        cp $(location :dlt-receive_as_host) $(@D)
        cp $(location :libdlt_as_host.so) $(@D)
        """,
    output_to_bindir = True,
    tags = ["aas"],
    tools = [
        ":dlt-receive_as_host",
        ":libdlt_as_host.so",
    ],
    visibility = ["//visibility:public"],
)

py_library(
    name = "dlt",
    srcs = [
        "__init__.py",
        "dlt_receive.py",
        "dlt_window.py",
    ],
    data = [":dlt-artifacts"],
    imports = ["."],
    visibility = ["//visibility:public"],
    deps = [
        "//itf/core/utils",
        "@python_dlt",
    ],
)
