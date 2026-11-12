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
load("@itf_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_binary", "py_library")

exports_files(["main.py"])

py_library(
    name = "cli",
    srcs = glob(["*.py"]),
    visibility = ["//visibility:public"],
    deps = [
        "//score/itf/compat",
        "//score/itf/contracts",
        "//score/itf/core",
        "//score/itf/core/adapters:definitions",
        "//score/itf/core/adapters:pytest",
        requirement("pytest"),
        requirement("pyyaml"),
    ],
)

# The command line with every pack of ITF on the path, so `plan`, `up` and `doctor` work for any target file
# made of ITF's own packs.
py_binary(
    name = "itf",
    srcs = ["main.py"],
    main = "main.py",
    visibility = ["//visibility:public"],
    deps = [
        ":cli",
        "//score/itf/core",
        "//score/itf/packs/core_dump",
        "//score/itf/packs/dlt",
        "//score/itf/packs/docker",
        "//score/itf/packs/localhost",
        "//score/itf/packs/net",
        "//score/itf/packs/pcap",
        "//score/itf/packs/ping",
        "//score/itf/packs/qemu",
        "//score/itf/packs/serial",
        "//score/itf/packs/sim",
        "//score/itf/packs/ssh",
    ],
)
