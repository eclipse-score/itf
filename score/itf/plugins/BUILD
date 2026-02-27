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
load("//bazel:py_itf_plugin.bzl", "py_itf_plugin")

py_library(
    name = "core",
    srcs = ["core.py"],
    visibility = ["//visibility:public"],
    deps = [
        "//score/itf/core/target",
        requirement("pytest"),
    ],
)

py_library(
    name = "docker",
    srcs = ["docker.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":core",
        "//score/itf/core/target",
        requirement("docker"),
        requirement("pytest"),
    ],
)

# ---- ITF plugin targets (used by py_itf_test symbolic macro) ----

py_itf_plugin(
    name = "docker_plugin",
    enabled_plugins = [
        "score.itf.plugins.docker",
    ],
    py_library = ":docker",
    visibility = ["//visibility:public"],
)

py_itf_plugin(
    name = "qemu_plugin",
    enabled_plugins = [
        "score.itf.plugins.qemu",
    ],
    py_library = "//score/itf/plugins/qemu",
    visibility = ["//visibility:public"],
)

py_itf_plugin(
    name = "dlt_plugin",
    enabled_plugins = [
        "score.itf.plugins.dlt",
    ],
    plugin_args = [
        "--dlt-receive-path=$(location @score_itf//third_party/dlt:dlt-receive)",
    ],
    plugin_data_as_exec = [
        "@score_itf//third_party/dlt:dlt-receive",
    ],
    py_library = "//score/itf/plugins/dlt",
    visibility = ["//visibility:public"],
)
