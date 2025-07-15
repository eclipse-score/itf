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
filegroup(
    name = "fg_dlt_headers",
    srcs = glob([
        "include/**/*.h",
    ]),
)

filegroup(
    name = "fg_dlt_receive_SRCS",
    srcs = ["src/console/dlt-receive.c"],
)

cc_library(
    name = "dlt_headers",
    hdrs = [":fg_dlt_headers"],
    features = ["third_party_warnings"],
    includes = ["include"],
)

cc_library(
    name = "dlt-library",
    srcs = glob(
        [
            "src/shared/**/*.c",
            "src/shared/**/*.h",
            "src/lib/**/*.c",
            "src/lib/**/*.h",
            "include/**/*.h",
        ],
    ) + [
        "src/daemon/dlt-daemon_cfg.h",
    ],
    hdrs = [":fg_dlt_headers"],
    copts = [
        "-pthread",
    ],
    defines = [
        "_GNU_SOURCE",
    ],
    features = ["third_party_warnings"],
    includes = [
        "include",
        "include/dlt",
        "src/daemon",
        "src/lib",
        "src/shared",
    ],
    linkopts = [
        "-pthread",
        "-lrt",
    ],
    deps = [
        ":dlt_headers",
    ],
    alwayslink = True,
)

cc_binary(
    name = "libdlt.so",
    features = ["third_party_warnings"],
    linkshared = True,
    visibility = ["//visibility:public"],
    deps = [
        ":dlt-library",
    ],
)

cc_binary(
    name = "dlt-receive",
    srcs = [":fg_dlt_receive_SRCS"],
    features = [
        "treat_warnings_as_errors",
        "strict_warnings",
        "additional_warnings",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":dlt-library",
    ],
)
