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
load("@rules_pkg//pkg:tar.bzl", "pkg_tar")

pkg_tar(
    name = "dlt-bins-pkg",
    srcs = [
        "@score_itf//third_party/dlt:dlt-adaptor-stdin",
        "@score_itf//third_party/dlt:dlt-daemon",
        "@score_itf//third_party/dlt:dlt-receive",
    ],
    package_dir = "usr/bin",
)

pkg_tar(
    name = "dlt-conf-pkg",
    srcs = [
        "@score_itf//third_party/dlt:dlt-daemon-conf",
    ],
    package_dir = "etc",
)

pkg_tar(
    name = "dlt-pkg",
    deps = [
        ":dlt-bins-pkg",
        ":dlt-conf-pkg",
    ],
)

oci_image(
    name = "image",
    base = "@ubuntu_24_04",
    tars = [
        ":dlt-pkg",
    ],
)

oci_tarball(
    name = "image_tarball",
    image = ":image",
    repo_tags = ["score_itf_examples:latest"],
    visibility = [
        "//test:__pkg__",
        # TODO: Should be only visibile to examples
        "//visibility:public",
        #"@score_itf_examples//:__subpackages__",
    ],
)
