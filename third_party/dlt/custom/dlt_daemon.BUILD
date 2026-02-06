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
load("@rules_cc//cc:defs.bzl", "cc_binary", "cc_library")

cc_library(
    name = "dlt-library",
    srcs = glob([
        "src/shared/**/*.c",
        "src/shared/**/*.h",
        "src/lib/**/*.c",
        "src/lib/**/*.h",
    ]) + [
        "src/daemon/dlt-daemon_cfg.h",
    ],
    hdrs = glob(["include/**/*.h"]),
    defines = [
        "_GNU_SOURCE",
    ],
    includes = [
        "include/dlt",
        "src/daemon",
        "src/lib",
        "src/shared",
    ],
    linkopts = [
        "-pthread",
        "-lrt",
    ],
)

cc_binary(
    name = "libdlt.so",
    linkshared = True,
    visibility = ["//visibility:public"],
    deps = [
        ":dlt-library",
    ],
)

cc_binary(
    name = "dlt-receive",
    srcs = ["src/console/dlt-receive.c"],
    deps = [
        ":dlt-library",
    ],
    visibility = ["//visibility:public"],
)

cc_binary(
    name = "dlt-adaptor-stdin",
    srcs = [
        "src/adaptor/dlt-adaptor-stdin.c",
    ],
    deps = [
        ":dlt-library",
    ],
    visibility = ["//visibility:public"],
)

cc_binary(
    name = "dlt-daemon",
    srcs = glob([
        "include/**/*.h",
        "src/daemon/*.h",
        "src/gateway/*.h",
        "src/lib/**/*.h",
        "src/offlinelogstorage/*.h",
        "src/shared/**/*.h",
    ]) + [
	"src/daemon/dlt-daemon.c",
	"src/daemon/dlt_daemon_client.c",
	"src/daemon/dlt_daemon_common.c",
	"src/daemon/dlt_daemon_connection.c",
	"src/daemon/dlt_daemon_event_handler.c",
	"src/daemon/dlt_daemon_offline_logstorage.c",
	"src/daemon/dlt_daemon_serial.c",
	"src/daemon/dlt_daemon_socket.c",
	"src/daemon/dlt_daemon_unix_socket.c",
	"src/gateway/dlt_gateway.c",
	"src/lib/dlt_client.c",
	"src/offlinelogstorage/dlt_offline_logstorage.c",
	"src/offlinelogstorage/dlt_offline_logstorage_behavior.c",
	"src/shared/dlt_common.c",
	"src/shared/dlt_config_file_parser.c",
	"src/shared/dlt_offline_trace.c",
	"src/shared/dlt_shm.c",
	"src/shared/dlt_user_shared.c",
    ],
    defines = [
        "_GNU_SOURCE",
        'CONFIGURATION_FILES_DIR=\\"/etc\\"',
    ],
    includes = [
        "include/dlt",
        "src/daemon",
        "src/gateway",
        "src/lib",
        "src/offlinelogstorage",
        "src/shared",
    ],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "dlt-daemon-conf",
    srcs = [
	"src/daemon/dlt.conf",
    ],
    visibility = ["//visibility:public"],
)
