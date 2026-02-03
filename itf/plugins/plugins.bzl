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

load("//bazel:py_itf_plugin.bzl", "py_itf_plugin")

docker = py_itf_plugin(
    py_library = "@score_itf//itf/plugins:docker",
    enabled_plugins = [
        "itf.plugins.docker",
    ],
    args = [
    ],
    data = [
    ],
    data_as_exec = [
    ],
    tags = [
    ],
)

base = py_itf_plugin(
    py_library = "@score_itf//itf/core/base",
    enabled_plugins = [
        "itf.core.base.base_plugin",
    ],
    args = [
        "--dlt_receive_path=$(location @score_itf//itf/core/dlt:dlt-receive_as_host)",
    ],
    data = [
    ],
    data_as_exec = [
        "@score_itf//itf/core/dlt:dlt-receive_as_host",
        "@score_itf//itf/core/dlt:libdlt_as_host.so",
    ],
    tags = [
        "local",
        "manual",
    ],
)
