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

load("@rules_cc//cc:cc_binary.bzl", "cc_binary")
load("@rules_pkg//pkg:mappings.bzl", "pkg_attributes", "pkg_files")
load("@score_rules_imagefs//rules/qnx:ifs.bzl", "qnx_ifs")

cc_binary(
    name = "udp_sender",
    srcs = ["udp_sender.c"],
    linkopts = select({
        "@platforms//os:qnx": ["-lsocket"],
        "//conditions:default": [],
    }),
    visibility = ["//test/integration:__pkg__"],
)

pkg_files(
    name = "udp_sender_files",
    srcs = [":udp_sender"],
    attributes = pkg_attributes(mode = "0755"),
    prefix = "/proc/boot",
)

qnx_ifs(
    name = "init",
    srcs = [":udp_sender_files"],
    build_file = "init.build",
    extra_build_files = ["tools.build"],
    tags = ["manual"],
    target_compatible_with = ["@platforms//os:qnx"],
    visibility = ["//visibility:public"],
)
