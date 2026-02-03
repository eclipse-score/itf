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
load("@rules_cc//cc:defs.bzl", "cc_binary", "cc_test")
load("@rules_pkg//pkg:tar.bzl", "pkg_tar")

cc_binary(
    name = "example-app",
    srcs = ["main.cpp"],
)

cc_test(
    name = "example-test",
    srcs = ["test.cpp"],
    deps = [
        "@googletest//:gtest",
        "@googletest//:gtest_main",
    ],
)

pkg_tar(
    name = "example-app-pkg",
    srcs = [
        "example-app",
    ],
    visibility = ["//examples/docker:__pkg__"],
)
