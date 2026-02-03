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
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_tarball")

oci_image(
    name = "image",
    base = "@ubuntu_24_04",
    tars = [
        "//examples/cpp:example-app-pkg",
    ],
)

oci_tarball(
    name = "image_tarball",
    image = ":image",
    repo_tags = ["score_itf_examples:latest"],
    visibility = ["//examples/itf:__pkg__"],
)
