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
load("@rules_python//python:defs.bzl", "py_library")
load("//bazel:py_itf_plugin.bzl", "py_itf_plugin")

# The original plugins' labels, flags and module paths, kept so existing BUILD files, command lines and imports
# stay valid. Every module here only re-exports from score.itf.compat or a pack (//test/integration/legacy:shims_test checks
# it); the layer itself is //score/itf/compat.

py_library(
    name = "core",
    srcs = [
        "__init__.py",
        "core.py",
    ],
    visibility = ["//visibility:public"],
    deps = ["//score/itf/compat"],
)

py_library(
    name = "docker",
    srcs = ["docker.py"],
    visibility = ["//visibility:public"],
    deps = [":core"],
)

py_library(
    name = "core_dump",
    srcs = ["core_dump.py"],
    visibility = ["//visibility:public"],
    deps = [":core"],
)

# Loaded first by every py_itf_test that names no itf_target, as the original rule loaded it.
py_itf_plugin(
    name = "core_plugin",
    enabled_plugins = ["score.itf.plugins.core"],
    py_library = ":core",
    visibility = ["//visibility:public"],
)

py_itf_plugin(
    name = "docker_plugin",
    enabled_plugins = ["score.itf.plugins.docker"],
    py_library = ":docker",
    visibility = ["//visibility:public"],
)

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

# Set with: bazel test --//score/itf/plugins:core_dumps_output_dir=/abs/path
string_flag(
    name = "core_dumps_output_dir",
    build_setting_default = "",
    visibility = ["//visibility:public"],
)

py_itf_plugin(
    name = "core_dump_plugin",
    enabled_plugins = ["score.itf.plugins.core_dump"],
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
    enabled_plugins = ["score.itf.plugins.qemu"],
    py_library = "//score/itf/plugins/qemu",
    visibility = ["//visibility:public"],
)

py_itf_plugin(
    name = "dlt_plugin",
    enabled_plugins = ["score.itf.plugins.dlt"],
    plugin_args = [
        "--dlt-receive-path=$(location @score_itf//third_party/dlt:dlt-receive)",
    ],
    plugin_data_as_exec = [
        "@score_itf//third_party/dlt:dlt-receive",
    ],
    py_library = "//score/itf/plugins/dlt",
    visibility = ["//visibility:public"],
)

alias(
    name = "attribute_plugin",
    actual = "//:attribute_plugin",
    visibility = ["//visibility:public"],
)
