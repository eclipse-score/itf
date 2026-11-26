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
load("//:defs.bzl", "py_itf_unittest")

exports_files(["pytest.ini"])

# The planner's own suites: OCTO and the extension seam (kinds).

py_itf_unittest(
    name = "octo_test",
    srcs = ["conftest.py"] + glob(["octo/*.py"]),
    pytest_config = "pytest.ini",
    deps = ["//score/itf/core/octo"],
)

py_itf_unittest(
    name = "kinds_test",
    srcs = ["conftest.py"] + glob(["kinds/*.py"]),
    pytest_config = "pytest.ini",
    deps = ["//score/itf/core/octo"],
)

test_suite(
    name = "core",
    tests = [
        ":kinds_test",
        ":octo_test",
    ],
)
