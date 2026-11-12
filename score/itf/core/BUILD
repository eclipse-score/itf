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
load("@rules_python//python:defs.bzl", "py_library")

# ITF core: engine, session, gating and the YAML frontend. Vocabulary-neutral (see the banned-words
# gate in //test/core/gates); domain code lives in packs.
py_library(
    name = "core",
    srcs = glob([
        "*.py",
        "engine/*.py",
        "frontends/*.py",
    ]),
    visibility = ["//visibility:public"],
    deps = [
        "//score/itf/core/octo",
        "//score/itf/core/process",
        requirement("pluggy"),
        requirement("pyyaml"),
    ],
)
