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

load("@itf_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_library")

py_library(
    name = "qemu",
    srcs = [
        "__init__.py",
        "base/__init__.py",
        "base/constants.py",
        "base/os/__init__.py",
        "base/os/config.py",
        "base/os/operating_system.py",
        "base/target/__init__.py",
        "base/target/base_target.py",
        "base/target/config/__init__.py",
        "base/target/config/base_processor.py",
        "base/target/config/config.py",
        "base/target/config/ecu.py",
        "base/target/config/performance_processor.py",
        "base/target/config/safety_processor.py",
        "base/target/processors/__init__.py",
        "base/target/processors/qemu_processor.py",
        "base/target/processors/safety_processor.py",
        "base/target/processors/target_processor.py",
        "base/target/qemu_target.py",
        "base/utils/__init__.py",
        "base/utils/exec_utils.py",
        "qemu.py",
        "qemu_process.py",
    ],
    imports = ["."],
    visibility = ["//visibility:public"],
    deps = [
        "//score/itf/core/process",
        "//score/itf/core/utils",
        requirement("netifaces"),
    ],
)
