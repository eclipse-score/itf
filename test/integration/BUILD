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
load("//:defs.bzl", "itf_target", "py_itf_test")

# One generic suite, many target files. Every test in suite/ (and specific/) is gated with @itf.requires on the
# roles it uses (`command`, `files`, ...): each test target below runs exactly the tests its target file supports,
# and lists the others as deselected with the reason. Adding a platform is adding a target file, an itf_target
# and a py_itf_test.
#
# Each itf_target compiles its target file during the build (`bazel build //test/integration:target_docker` writes
# target_docker.plan.json, or fails with ITF's diagnostics). legacy/ holds main's tests on the compatibility layer.

SUITE = glob(["suite/*.py"])

OBSERVABILITY_SUITE = [
    "suite/test_command.py",
    "suite/test_console.py",
]

PCAP_SUITE = ["suite/test_capture.py"]

itf_target(
    name = "target_qemu_observability_pcap",
    src = "targets/observability/qnx.itf.yaml",
    srcs = [
        "targets/observability/policy.py",
    ],
    files = {
        "ITF_QEMU_CONFIG": "//test/resources:qemu_bridge_config",
        "ITF_QEMU_KERNEL": "//test/resources/qnx:init",
    },
    packs = [
        "//score/itf/packs/qemu",
        "//score/itf/packs/ssh",
        "//score/itf/packs/pcap",
    ],
    tags = ["manual"],
    tools = {"ITF_TCPDUMP": "//score/itf/packs/pcap:tcpdump_bin"},
)

itf_target(
    name = "target_qemu_observability",
    src = "targets/observability/qnx_no_pcap.itf.yaml",
    srcs = [
        "targets/observability/policy.py",
    ],
    files = {
        "ITF_QEMU_CONFIG": "//test/resources:qemu_bridge_config",
        "ITF_QEMU_KERNEL": "//test/resources/qnx:init",
    },
    packs = [
        "//score/itf/packs/qemu",
        "//score/itf/packs/ssh",
    ],
    tags = ["manual"],
)

itf_target(
    name = "target_qemu_serial_observability_pcap",
    src = "targets/observability/qnx.itf.yaml",
    srcs = [
        "targets/observability/policy.py",
    ],
    files = {
        "ITF_QEMU_CONFIG": "//test/resources:qemu_bridge_config",
        "ITF_QEMU_KERNEL": "//test/resources/qnx:init",
    },
    overrides = ["overrides/qemu_serial.itf.yaml"],
    packs = [
        "//score/itf/packs/qemu",
        "//score/itf/packs/ssh",
        "//score/itf/packs/pcap",
        "//score/itf/packs/serial",
    ],
    tags = ["manual"],
    tools = {"ITF_TCPDUMP": "//score/itf/packs/pcap:tcpdump_bin"},
)

itf_target(
    name = "target_qemu_serial_observability",
    src = "targets/observability/qnx_no_pcap.itf.yaml",
    srcs = [
        "targets/observability/policy.py",
    ],
    data = glob(["targets/**/*.itf.yaml"]),
    files = {
        "ITF_QEMU_CONFIG": "//test/resources:qemu_bridge_config",
        "ITF_QEMU_KERNEL": "//test/resources/qnx:init",
    },
    overrides = ["overrides/qemu_serial.itf.yaml"],
    packs = [
        "//score/itf/packs/qemu",
        "//score/itf/packs/ssh",
        "//score/itf/packs/serial",
    ],
    tags = ["manual"],
)

itf_target(
    name = "target_docker_observability_pcap",
    src = "targets/observability/docker.itf.yaml",
    srcs = ["targets/observability/policy.py"],
    files = {"ITF_UDP_SENDER": "//test/resources/qnx:udp_sender"},
    packs = [
        "//score/itf/packs/docker",
        "//score/itf/packs/pcap",
    ],
    tags = ["manual"],
    tools = {"ITF_TCPDUMP": "//score/itf/packs/pcap:tcpdump_bin"},
)

itf_target(
    name = "target_docker_observability",
    src = "targets/observability/docker_no_pcap.itf.yaml",
    srcs = ["targets/observability/policy.py"],
    files = {"ITF_UDP_SENDER": "//test/resources/qnx:udp_sender"},
    packs = [
        "//score/itf/packs/docker",
    ],
    tags = ["manual"],
)

py_itf_test(
    name = "observability",
    timeout = "long",
    srcs = ["conftest.py"] + OBSERVABILITY_SUITE,
    tags = ["manual"],
    target = select({
        "@platforms//os:qnx": ":target_qemu_observability",
        "//conditions:default": ":target_docker_observability",
    }),
)

py_itf_test(
    name = "observability_pcap",
    timeout = "long",
    srcs = ["conftest.py"] + PCAP_SUITE,
    tags = [
        "local",
        "manual",
    ],
    target = select({
        "@platforms//os:qnx": ":target_qemu_observability_pcap",
        "//conditions:default": ":target_docker_observability_pcap",
    }),
)

py_itf_test(
    name = "observability_serial",
    timeout = "long",
    srcs = ["conftest.py"] + OBSERVABILITY_SUITE,
    tags = ["manual"],
    target = ":target_qemu_serial_observability",
)

py_itf_test(
    name = "observability_serial_pcap",
    timeout = "long",
    srcs = ["conftest.py"] + PCAP_SUITE,
    tags = [
        "local",
        "manual",
    ],
    target = ":target_qemu_serial_observability_pcap",
)

py_itf_test(
    name = "qemu_observability_specialist",
    timeout = "long",
    srcs = [
        "conftest.py",
        "specific/test_qemu_observability.py",
    ],
    tags = [
        "manual",
        "qemu",
    ],
    target = ":target_qemu_observability_pcap",
)

# ---- the test host: runs anywhere, no daemon

itf_target(
    name = "target_localhost",
    src = "targets/localhost.itf.yaml",
    srcs = ["targets/policy.py"],
    data = glob(["targets/**/*.itf.yaml"]),
    packs = ["//score/itf/packs/localhost"],
)

py_itf_test(
    name = "localhost",
    timeout = "long",
    srcs = ["conftest.py"] + SUITE,
    target = ":target_localhost",
    target_compatible_with = ["@platforms//os:linux"],
)

py_itf_test(
    name = "conformance_localhost",
    timeout = "long",
    srcs = [
        "conformance/test_conformance.py",
        "conftest.py",
    ],
    plugins = ["//score/itf/contracts:conformance"],
    target = ":target_localhost",
    target_compatible_with = ["@platforms//os:linux"],
)

# The same host with an override file: the facts of one setup (the platform's working directory).
itf_target(
    name = "target_localhost_override",
    src = "targets/localhost.itf.yaml",
    srcs = ["targets/policy.py"],
    data = glob(["targets/**/*.itf.yaml"]),
    overrides = ["overrides/localhost.itf.yaml"],
    packs = ["//score/itf/packs/localhost"],
)

py_itf_test(
    name = "localhost_override",
    timeout = "long",
    srcs = ["conftest.py"] + SUITE + [
        "specific/test_override_values.py",
    ],
    target = ":target_localhost_override",
    target_compatible_with = ["@platforms//os:linux"],
)

# The host with a core dump collector over its command and files roles.
itf_target(
    name = "target_core_dump",
    src = "targets/core_dump/core_dump.itf.yaml",
    srcs = ["targets/policy.py"],
    data = glob(["targets/**/*.itf.yaml"]),
    packs = [
        "//score/itf/packs/localhost",
        "//score/itf/packs/core_dump",
    ],
)

py_itf_test(
    name = "core_dump",
    timeout = "long",
    srcs = ["conftest.py"] + SUITE,
    target = ":target_core_dump",
    target_compatible_with = ["@platforms//os:linux"],
)

# ---- a serial console on a pty shell: runs anywhere, no hardware

itf_target(
    name = "target_serial",
    src = "targets/serial/serial.itf.yaml",
    srcs = ["targets/policy.py"],
    data = glob(["targets/**/*.itf.yaml"]),
    packs = ["//score/itf/packs/serial"],
)

py_itf_test(
    name = "serial",
    timeout = "long",
    srcs = ["conftest.py"] + SUITE,
    target = ":target_serial",
    target_compatible_with = ["@platforms//os:linux"],
)

py_itf_test(
    name = "conformance_serial",
    timeout = "long",
    srcs = [
        "conformance/test_conformance.py",
        "conftest.py",
    ],
    plugins = ["//score/itf/contracts:conformance"],
    target = ":target_serial",
    target_compatible_with = ["@platforms//os:linux"],
)

# ---- containers (Docker or rootless Podman)

# A container through the Docker API only.
itf_target(
    name = "target_docker",
    src = "targets/docker/docker.itf.yaml",
    srcs = ["targets/policy.py"],
    data = glob(["targets/**/*.itf.yaml"]),
    env = {
        "SSH_PASSWORD": "score",  # the demo container's own account
        "SSH_USER": "score",
    },
    # The volume the container mounts: one of the target's own files, so it is in the runfiles of every test of the
    # target (the suite and the conformance run). A missing bind source would be created by a rootful Docker
    # daemon, as root, inside the test's sandbox.
    files = {"ITF_EXTRA_MOUNT": "targets/docker/docker.itf.yaml"},
    packs = ["//score/itf/packs/docker"],
    tags = ["requires-docker"],
)

py_itf_test(
    name = "docker",
    timeout = "long",
    srcs = ["conftest.py"] + SUITE + [
        "specific/test_container.py",
    ],
    tags = ["requires-docker"],
    target = ":target_docker",
    target_compatible_with = ["@platforms//os:linux"],
)

py_itf_test(
    name = "conformance_docker",
    timeout = "long",
    srcs = [
        "conformance/test_conformance.py",
        "conftest.py",
    ],
    plugins = ["//score/itf/contracts:conformance"],
    tags = ["requires-docker"],
    target = ":target_docker",
    target_compatible_with = ["@platforms//os:linux"],
)

# A container running sshd: SSH, SFTP and a shell session.
itf_target(
    name = "target_docker_ssh",
    src = "targets/docker_ssh/docker_ssh.itf.yaml",
    srcs = ["targets/policy.py"],
    data = glob(["targets/**/*.itf.yaml"]),
    env = {
        "SSH_PASSWORD": "score",  # the demo container's own account
        "SSH_USER": "score",
    },
    # The volume the container mounts: one of the target's own files, so it is in the runfiles of every test of the
    # target (the suite and the conformance run). A missing bind source would be created by a rootful Docker
    # daemon, as root, inside the test's sandbox.
    files = {"ITF_EXTRA_MOUNT": "targets/docker_ssh/docker_ssh.itf.yaml"},
    packs = [
        "//score/itf/packs/docker",
        "//score/itf/packs/net",
        "//score/itf/packs/ssh",
    ],
    tags = ["requires-docker"],
)

# The same suite over SSH: on the sshd container, or on the QNX machine when building for QNX
# (--config=qemu-integration); a select() picks the target, as main's test_ssh_configurable picked the plugin.
py_itf_test(
    name = "ssh",
    timeout = "long",
    srcs = ["conftest.py"] + SUITE + [
        "specific/test_container.py",
        "specific/test_second_login.py",
    ],
    tags = ["requires-docker"],
    target = select({
        "@platforms//os:qnx": ":target_qnx_bridge",
        "//conditions:default": ":target_docker_ssh",
    }),
)

py_itf_test(
    name = "conformance_docker_ssh",
    timeout = "long",
    srcs = [
        "conformance/test_conformance.py",
        "conftest.py",
    ],
    plugins = ["//score/itf/contracts:conformance"],
    tags = ["requires-docker"],
    target = ":target_docker_ssh",
    target_compatible_with = ["@platforms//os:linux"],
)

# A dlt-daemon container: DLT received on the host over TCP, and dlt-receive run on the container.
itf_target(
    name = "target_dlt_receive",
    src = "targets/dlt_receive/dlt_receive.itf.yaml",
    srcs = ["targets/policy.py"],
    data = glob(["targets/**/*.itf.yaml"]),
    env = {
        "ITF_DLT_PORT": "13490",  # the daemon's port, published as is
    },
    files = {
        "ITF_IMAGE_LOAD": "//test/resources:image_load",
    },
    packs = [
        "//score/itf/packs/docker",
        "//score/itf/packs/dlt",
    ],
    tags = ["requires-docker"],
)

py_itf_test(
    name = "dlt_receive",
    timeout = "long",
    srcs = ["conftest.py"] + SUITE + [
        "specific/test_dlt_on_target.py",
    ],
    tags = ["requires-docker"],
    target = ":target_dlt_receive",
    target_compatible_with = ["@platforms//os:linux"],
)

# ---- QEMU machines: qemu-system-*, /dev/kvm; manual, run with --config=qemu-integration[-linux]

# QNX on a bridged network, with a second login (qnx.itf.yaml): the `ssh` test runs on it when building for QNX.
itf_target(
    name = "target_qnx_bridge",
    src = "targets/qnx/qnx.itf.yaml",
    srcs = ["targets/policy.py"],
    data = glob(["targets/**/*.itf.yaml"]),
    files = {
        "ITF_QEMU_CONFIG": "//test/resources:qemu_bridge_config",
        "ITF_QEMU_KERNEL": "//test/resources/qnx:init",
    },
    packs = [
        "//score/itf/packs/net",
        "//score/itf/packs/ping",
        "//score/itf/packs/qemu",
        "//score/itf/packs/ssh",
    ],
    tags = ["manual"],
)

# QNX behind port forwarding.
itf_target(
    name = "target_qnx_port_forwarding",
    src = "targets/qnx/qnx.itf.yaml",
    srcs = ["targets/policy.py"],
    data = glob(["targets/**/*.itf.yaml"]),
    files = {
        "ITF_QEMU_CONFIG": "//test/resources:qemu_port_forwarding_config",
        "ITF_QEMU_KERNEL": "//test/resources/qnx:init",
    },
    packs = [
        "//score/itf/packs/net",
        "//score/itf/packs/ping",
        "//score/itf/packs/qemu",
        "//score/itf/packs/ssh",
    ],
    tags = ["manual"],
)

py_itf_test(
    name = "qnx_port_forwarding",
    timeout = "long",
    srcs = ["conftest.py"] + SUITE + [
        "specific/test_second_login.py",
    ],
    tags = ["manual"],
    target = ":target_qnx_port_forwarding",
    target_compatible_with = ["@platforms//os:linux"],
)

# Ubuntu with a second disk.
itf_target(
    name = "target_ubuntu",
    src = "targets/ubuntu/ubuntu.itf.yaml",
    srcs = [
        "targets/policy.py",
        "targets/ubuntu/policy.py",
    ],
    data = glob(["targets/**/*.itf.yaml"]),
    files = {
        "ITF_QEMU_CONFIG": "@os_images//ubuntu_x86_64:qemu_config",
        "ITF_QEMU_DISK": "//test/resources:qemu_disk_image",
        "ITF_QEMU_ROOTFS": "@os_images//ubuntu_x86_64:image",
    },
    packs = [
        "//score/itf/packs/ping",
        "//score/itf/packs/qemu",
        "//score/itf/packs/ssh",
    ],
    tags = ["manual"],
)

py_itf_test(
    name = "ubuntu",
    timeout = "long",
    srcs = ["conftest.py"] + SUITE + [
        "specific/test_disk.py",
    ],
    tags = ["manual"],
    target = ":target_ubuntu",
    target_compatible_with = ["@platforms//os:linux"],
)

# EB corbos Linux for Safety Applications (aarch64) with a second disk.
itf_target(
    name = "target_ebclfsa",
    src = "targets/qemu.itf.yaml",
    srcs = ["targets/policy.py"],
    data = glob(["targets/**/*.itf.yaml"]),
    files = {
        "ITF_QEMU_CONFIG": "@os_images//ebclfsa_aarch64:qemu_config",
        "ITF_QEMU_DISK": "//test/resources:qemu_disk_image",
        "ITF_QEMU_KERNEL": "@os_images//ebclfsa_aarch64:kernel",
        "ITF_QEMU_ROOTFS": "@os_images//ebclfsa_aarch64:image",
    },
    packs = [
        "//score/itf/packs/ping",
        "//score/itf/packs/qemu",
        "//score/itf/packs/ssh",
    ],
    tags = ["manual"],
)

py_itf_test(
    name = "ebclfsa",
    timeout = "long",
    srcs = ["conftest.py"] + SUITE + [
        "specific/test_disk.py",
    ],
    tags = ["manual"],
    target = ":target_ebclfsa",
    target_compatible_with = ["@platforms//os:linux"],
)

# Run with --config=qemu-integration: `ssh` then runs on the QNX machine (its select()).
test_suite(
    name = "qnx_qemu_tests",
    tags = ["manual"],
    tests = [
        ":qnx_port_forwarding",
        ":ssh",
    ],
)

test_suite(
    name = "linux_qemu_tests",
    tags = ["manual"],
    tests = [
        ":ebclfsa",
        ":ubuntu",
    ],
)

# Every target file here and its policy, for //test/plans:shipped_targets_test, which compiles each one without
# building its files: the QEMU targets above are manual, so no build compiles them otherwise.
filegroup(
    name = "target_files",
    srcs = glob([
        "targets/**/*.itf.yaml",
        "targets/**/*policy.py",
    ]),
    visibility = ["//test/plans:__pkg__"],
)
