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
load("//score/itf/plugins:plugins.bzl", "dlt", "docker", "qemu")

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
    name = "test_ssh",
    srcs = [
        "test_ssh.py",
    ],
    args = [
        "--docker-image=linuxserver/openssh-server:version-10.2_p1-r0",
    ],
    plugins = [
        docker,
    ],
)

py_itf_test(
    name = "test_qemu_bridge_network",
    srcs = [
        "test_qemu.py",
    ],
    args = [
        "--target_config=$(location //test/resources:target_config)",
        "--dlt-config=$(location //test/resources:dlt_config)",
        "--ecu=s_core_ecu_qemu_bridge_network",
        "--qemu",
    ],
    data = [
        "//test/resources:dlt_config",
        "//test/resources:target_config",
    ],
    plugins = [
        qemu,
        dlt,
    ],
    tags = [
        "local",
        "manual",
    ],
)

py_itf_test(
    name = "test_qemu_bridge_network_no_dlt",
    srcs = [
        "test_qemu.py",
    ],
    args = [
        "--target_config=$(location //test/resources:target_config)",
        "--ecu=s_core_ecu_qemu_bridge_network",
        "--qemu",
    ],
    data = [
        "//test/resources:target_config",
    ],
    plugins = [
        qemu,
    ],
    tags = [
        "local",
        "manual",
    ],
)

py_itf_test(
    name = "test_qemu_port_forwarding",
    srcs = [
        "test_qemu.py",
    ],
    args = [
        "--target_config=$(location //test/resources:target_config)",
        "--ecu=s_core_ecu_qemu_port_forwarding",
        "--qemu",
    ],
    data = [
        "//test/resources:target_config",
    ],
    plugins = [
        qemu,
        dlt,
    ],
    tags = [
        "local",
        "manual",
    ],
)
