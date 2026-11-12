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

# Pack unit tests: each may import its own pack's internals; packs never import each other.

py_itf_unittest(
    name = "pcap_test",
    srcs = ["test_pcap.py"],
    deps = ["//score/itf/packs/pcap:lib"],
)

py_itf_unittest(
    name = "ssh_legacy_api_test",
    srcs = ["test_ssh_legacy_api.py"],
    deps = ["//score/itf/packs/ssh:lib"],
)

py_itf_unittest(
    name = "qemu_test",
    srcs = glob(["qemu/*.py"]),
    data = [
        "//test/resources:qemu_bridge_config",
        "//test/resources:qemu_port_forwarding_config",
    ],
    target_compatible_with = ["@platforms//os:linux"],
    deps = [
        "//score/itf/packs/qemu:lib",
        "@rules_python//python/runfiles",
    ],
)

py_itf_unittest(
    name = "ping_test",
    srcs = glob(["ping/*.py"]),
    deps = ["//score/itf/packs/ping:lib"],
)

py_itf_unittest(
    name = "docker_test",
    srcs = glob(["docker/*.py"]),
    deps = ["//score/itf/packs/docker:lib"],
)

py_itf_unittest(
    name = "serial_test",
    srcs = glob(["serial/*.py"]),
    deps = ["//score/itf/packs/serial:lib"],
)

py_itf_unittest(
    name = "dlt_test",
    srcs = glob(["dlt/*.py"]),
    target_compatible_with = ["@platforms//os:linux"],
    deps = ["//score/itf/packs/dlt:lib"],
)

py_itf_unittest(
    name = "core_dump_test",
    srcs = glob(["core_dump/*.py"]),
    deps = ["//score/itf/packs/core_dump:lib"],
)

py_itf_unittest(
    name = "sim_test",
    srcs = glob(["sim/*.py"]),
    deps = [
        "//score/itf/core",
        "//score/itf/packs/net:lib",
        "//score/itf/packs/sim:lib",
    ],
)

py_itf_unittest(
    name = "catalog_test",
    srcs = glob(["catalog/*.py"]),
    data = [
        "//:docs/_generated/catalog.html",
        "//:docs/reference/contracts.md",
    ],
    deps = [
        "//score/itf/contracts",
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

py_itf_unittest(
    name = "import_light_test",
    srcs = ["test_import_light.py"],
    deps = [
        "//score/itf/packs/core_dump",
        "//score/itf/packs/dlt",
        "//score/itf/packs/docker",
        "//score/itf/packs/localhost",
        "//score/itf/packs/net",
        "//score/itf/packs/pcap",
        "//score/itf/packs/ping",
        "//score/itf/packs/qemu",
        "//score/itf/packs/serial",
        "//score/itf/packs/ssh",
    ],
)
