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
load("@score_itf//itf/plugins:plugins.bzl", "base", "dlt", "docker")

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
    name = "test_ssh_bridge_network",
    srcs = [
        "test_ssh.py",
    ],
    args = [
        "--target_config=$(location @score_itf//config)",
        "--ecu=s_core_ecu_qemu_bridge_network",
        "--qemu",
    ],
    data = [
        "@score_itf//config",
    ],
    plugins = [
        base,
        dlt,
    ],
)

py_itf_test(
    name = "test_ssh_port_forwarding",
    srcs = [
        "test_ssh.py",
    ],
    args = [
        "--target_config=$(location @score_itf//config)",
        "--ecu=s_core_ecu_qemu_port_forwarding",
        "--qemu",
    ],
    data = [
        "@score_itf//config",
    ],
    plugins = [
        base,
        dlt,
    ],
)
