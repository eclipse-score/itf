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
load("@score_itf//:defs.bzl", "py_itf_test")
load("@score_itf//score/itf/plugins:plugins.bzl", "dlt", "docker", "qemu")

py_itf_test(
    name = "test_docker",
    srcs = [
        "test_docker.py",
    ],
    args = [
        "--docker-image-bootstrap=$(location //examples/docker:image_tarball)",
        "--docker-image=score_itf_examples:latest",
    ],
    data = ["//examples/docker:image_tarball"],
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
        "--docker-image-bootstrap=$(location @score_itf//test/resources:image_tarball)",
        "--docker-image=score_itf_examples:latest",
    ],
    data = ["@score_itf//test/resources:image_tarball"],
    plugins = [
        dlt,
        docker,
    ],
)

py_itf_test(
    name = "test_qemu_ssh_bridge_network",
    srcs = [
        "test_qemu.py",
    ],
    args = [
        "--qemu-config=$(location @score_itf//test/resources:qemu_bridge_config)",
        "--qemu-image=$(location //examples/itf/qnx:init)",
    ],
    data = [
        "//examples/itf/qnx:init",
        "@score_itf//test/resources:qemu_bridge_config",
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
    name = "test_qemu_ssh_port_forwarding",
    srcs = [
        "test_qemu.py",
    ],
    args = [
        "--qemu-config=$(location @score_itf//test/resources:qemu_port_forwarding_config)",
        "--qemu-image=$(location //examples/itf/qnx:init)",
    ],
    data = [
        "//examples/itf/qnx:init",
        "@score_itf//test/resources:qemu_port_forwarding_config",
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
