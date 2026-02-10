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
load("//score/itf/plugins:plugins.bzl", "base", "dlt", "docker")

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
    args = [
        "--docker-image-bootstrap=$(location //test/resources:image_tarball)",
        "--docker-image=score_itf_examples:latest",
    ],
    data = ["//test/resources:image_tarball"],
    plugins = [
        dlt,
        docker,
    ],
)

py_itf_test(
    name = "test_ssh_bridge_network",
    srcs = [
        "test_ssh.py",
    ],
    args = [
        "--target_config=$(location //config)",
        "--dlt-config=$(location dlt_config.json)",
        "--ecu=s_core_ecu_qemu_bridge_network",
        "--qemu",
    ],
    data = [
        "dlt_config.json",
        "//config",
    ],
    plugins = [
        base,
        dlt,
    ],
    tags = [
        "local",
        "manual",
    ],
)

py_itf_test(
    name = "test_ssh_bridge_network_no_dlt",
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
    tags = [
        "local",
        "manual",
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
        dlt,
    ],
    tags = [
        "local",
        "manual",
    ],
)
