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
load("@bazel_skylib//rules:common_settings.bzl", "bool_flag", "string_flag")
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

py_library(
    name = "core_dump",
    srcs = ["core_dump.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":core",
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

# ---- Core dump plugin (works with any target that has exec + file_transfer) ----

# Enable core dump extraction. Works with both docker_plugin and qemu_plugin.
# Toggle with: bazel test --//score/itf/plugins:extract_core_dumps
bool_flag(
    name = "extract_core_dumps",
    build_setting_default = False,
    visibility = ["//visibility:public"],
)

config_setting(
    name = "extract_core_dump_enabled",
    flag_values = {":extract_core_dumps": "True"},
    visibility = ["//visibility:public"],
)

# Override the output directory for extracted core dumps.
# Set with: bazel test --//score/itf/plugins:core_dumps_output_dir=/abs/path
string_flag(
    name = "core_dumps_output_dir",
    build_setting_default = "",
    visibility = ["//visibility:public"],
)

py_itf_plugin(
    name = "core_dump_plugin",
    enabled_plugins = [
        "score.itf.plugins.core_dump",
    ],
    plugin_args = select({
        ":extract_core_dump_enabled": ["--extract-core-dumps"],
        "//conditions:default": [],
    }),
    py_library = ":core_dump",
    string_flag_args = {
        ":core_dumps_output_dir": "--core-dumps-output-dir={}",
    },
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

py_itf_plugin(
    name = "attribute_plugin",
    enabled_plugins = [
        "attribute_plugin",
    ],
    py_library = "@score_tooling//python_basics/score_pytest:attribute_plugin",
    visibility = ["//visibility:public"],
)
