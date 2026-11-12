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
load("@rules_python//python:defs.bzl", "py_binary", "py_test")

# ITF without pytest: `run.py` builds a Session from plain Python, composes the target from
# targets/target.itf.yaml, brings it up, uses `target` and closes. See README.md.

DEPS = [
    "@score_itf//:itf",
    "@score_itf//score/itf/packs/localhost",
]

py_binary(
    name = "run",
    srcs = ["run.py"],
    data = ["targets/target.itf.yaml"],
    imports = ["."],
    main = "run.py",
    deps = DEPS,
)

py_test(
    name = "run_test",
    srcs = ["run.py"],
    data = ["targets/target.itf.yaml"],
    imports = ["."],
    main = "run.py",
    deps = DEPS,
)
