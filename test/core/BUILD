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
load("//:defs.bzl", "py_itf_unittest")

PACKS = [
    "core_dump",
    "dlt",
    "docker",
    "localhost",
    "net",
    "pcap",
    "ping",
    "qemu",
    "serial",
    "sim",
    "ssh",
]

exports_files(["pytest.ini"])

# The framework's own suites: planner (octo), engine and pytest adapter
# (itf), the extension seam (kinds) and the product-split gates.

py_itf_unittest(
    name = "octo_test",
    srcs = ["conftest.py"] + glob(["octo/*.py"]),
    pytest_config = "pytest.ini",
)

py_itf_unittest(
    name = "kinds_test",
    srcs = ["conftest.py"] + glob(["kinds/*.py"]),
    pytest_config = "pytest.ini",
)

py_itf_unittest(
    name = "itf_test",
    srcs = ["conftest.py"] + glob([
        "itf/*.py",
        "itf/fixtures/*.py",
    ]),
    # Stands in for the pytest11 entry point a pip install would register: every pytest run in the
    # suite, including pytester's inner ones, loads the adapter.
    env = {"PYTEST_PLUGINS": "score.itf.core.adapters.pytest.plugin"},
    pytest_config = "pytest.ini",
    deps = [
        "//score/itf/core/adapters:pytest",
        "//score/itf/packs/localhost",
    ],
)

py_itf_unittest(
    name = "gates_test",
    srcs = ["conftest.py"] + glob(["gates/*.py"]),
    data = [
        "//score/itf/core/octo:README.md",
        "//tools/gates:wordlists",
    ] + glob(["octo/*.py"]) + [
        "//score/itf/packs/%s:sources" % pack
        for pack in PACKS
    ],
    pytest_config = "pytest.ini",
    deps = [
        requirement("pyyaml"),
    ],
)

test_suite(
    name = "core",
    tests = [
        ":gates_test",
        ":itf_test",
        ":kinds_test",
        ":octo_test",
    ],
)
