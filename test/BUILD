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
load("//:defs.bzl", "py_itf_test")
load("//itf/plugins:plugins.bzl", "base", "docker")

py_itf_test(
    name = "test_rules_are_working_correctly",
    srcs = [
        "conftest.py",
        "test_rules_are_working_correctly.py",
    ],
)

py_itf_test(
    name = "test_docker",
    srcs = [
        "test_docker.py",
    ],
    args = [
        "--docker-image=ubuntu:24.04",
    ],
    plugins = [
        docker,
    ],
)

py_itf_test(
    name = "test_dlt",
    srcs = [
        "test_dlt.py",
    ],
    deps = [
        "//itf/core/dlt",
    ],
)

py_itf_test(
    name = "test_ssh_bridge_network",
    srcs = [
        "test_ssh.py",
    ],
    args = [
        "--target_config=$(location //config)",
        "--ecu=s_core_ecu_qemu_bridge_network",
        "--qemu",
    ],
    data = [
        "//config",
    ],
    plugins = [
        base,
    ],
)

py_itf_test(
    name = "test_ssh_port_forwarding",
    srcs = [
        "test_ssh.py",
    ],
    args = [
        "--target_config=$(location //config)",
        "--ecu=s_core_ecu_qemu_port_forwarding",
        "--qemu",
    ],
    data = [
        "//config",
    ],
    plugins = [
        base,
    ],
)
