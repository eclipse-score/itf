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
        "//score/itf/plugins:docker_plugin",
    ],
)

py_itf_test(
    name = "test_dlt",
    srcs = [
        "test_dlt.py",
    ],
    args = [
        "--docker-image-bootstrap=$(location //test/resources:image_load)",
        "--docker-image=score_itf_examples:latest",
    ],
    data = ["//test/resources:image_load"],
    plugins = [
        "//score/itf/plugins:dlt_plugin",
        "//score/itf/plugins:docker_plugin",
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
        "//score/itf/plugins:docker_plugin",
    ],
)

py_itf_test(
    name = "test_ssh_configurable",
    srcs = [
        "test_ssh.py",
    ],
    args = select(
        {
            "@platforms//os:qnx": [
                "--qemu-config=$(location //test/resources:qemu_bridge_config)",
                "--qemu-image=$(location //test/resources/qnx:init)",
            ],
            "//conditions:default": [
                "--docker-image=linuxserver/openssh-server:version-10.2_p1-r0",
            ],
        },
    ),
    data = select(
        {
            "@platforms//os:qnx": [
                "//test/resources:qemu_bridge_config",
                "//test/resources/qnx:init",
            ],
            "//conditions:default": [],
        },
    ),
    plugins = select(
        {
            "@platforms//os:qnx": [
                "//score/itf/plugins:qemu_plugin",
            ],
            "//conditions:default": [
                "//score/itf/plugins:docker_plugin",
            ],
        },
    ),
)

py_itf_test(
    name = "test_qemu_bridge_network",
    srcs = [
        "test_qemu.py",
    ],
    args = [
        "--qemu-config=$(location //test/resources:qemu_bridge_config)",
        "--qemu-image=$(location //test/resources/qnx:init)",
        "--dlt-config=$(location //test/resources:dlt_config)",
    ],
    data = [
        "//test/resources:dlt_config",
        "//test/resources:qemu_bridge_config",
        "//test/resources/qnx:init",
    ],
    plugins = [
        "//score/itf/plugins:qemu_plugin",
        "//score/itf/plugins:dlt_plugin",
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
        "--qemu-config=$(location //test/resources:qemu_bridge_config)",
        "--qemu-image=$(location //test/resources/qnx:init)",
    ],
    data = [
        "//test/resources:qemu_bridge_config",
        "//test/resources/qnx:init",
    ],
    plugins = [
        "//score/itf/plugins:qemu_plugin",
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
        "--qemu-config=$(location //test/resources:qemu_port_forwarding_config)",
        "--qemu-image=$(location //test/resources/qnx:init)",
    ],
    data = [
        "//test/resources:qemu_port_forwarding_config",
        "//test/resources/qnx:init",
    ],
    plugins = [
        "//score/itf/plugins:qemu_plugin",
        "//score/itf/plugins:dlt_plugin",
    ],
    tags = [
        "local",
        "manual",
    ],
)

py_itf_test(
    name = "test_ping",
    srcs = [
        "test_ping.py",
    ],
)

py_itf_test(
    name = "test_qemu_config_schema",
    srcs = [
        "test_qemu_config_schema.py",
    ],
    data = [
        "//test/resources:qemu_bridge_config",
        "//test/resources:qemu_port_forwarding_config",
    ],
    deps = [
        "//score/itf/plugins/qemu",
        "@rules_python//python/runfiles",
    ],
)
