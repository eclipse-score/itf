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
load("@score_itf//:defs.bzl", "itf_target", "py_itf_test")

# One test file (test_exec.py) on four targets. Each test asks for the roles it uses (`command`, `files`,
# `console`), so a target runs the tests its target file supports and lists the others as deselected, with
# the reason. Each target has a directory (`targets/<name>/<name>.itf.yaml`) saying what it is made of; the
# shared targets/policy.py keeps the code (readiness checks, evidence, the action that waits for the fake ECU)
# and is not listed by tests.
#
# `bazel build //examples/exec_everywhere:target_container` compiles a target file and writes
# `target_container.plan.json`: the roles, the wiring and the ordered actions, before anything exists.

# A plain container, reached through the container API.
itf_target(
    name = "target_container",
    src = "targets/container/container.itf.yaml",
    srcs = ["targets/policy.py"],
    packs = ["@score_itf//score/itf/packs/docker"],
)

py_itf_test(
    name = "container",
    srcs = ["test_exec.py"],
    target = ":target_container",
)

# The ssh starter's container, reached over SSH. The demo container's own account: not a secret.
itf_target(
    name = "target_ssh",
    src = "targets/ssh/ssh.itf.yaml",
    srcs = [
        "targets/policy.py",
        "//examples/starter/ssh:targets/policy.py",
    ],
    data = ["//examples/starter/ssh:targets/target.itf.yaml"],  # ssh.itf.yaml includes the ssh starter
    env = {
        "SSH_PASSWORD": "score",
        "SSH_USER": "score",
    },
    packs = [
        "@score_itf//score/itf/packs/docker",
        "@score_itf//score/itf/packs/net",
        "@score_itf//score/itf/packs/ssh",
    ],
)

py_itf_test(
    name = "ssh",
    srcs = ["test_exec.py"],
    target = ":target_ssh",
)

# A serial console on a pty shell: no hardware.
itf_target(
    name = "target_serial",
    src = "targets/serial/serial.itf.yaml",
    srcs = ["targets/policy.py"],
    packs = ["@score_itf//score/itf/packs/serial"],
)

py_itf_test(
    name = "serial",
    srcs = ["test_exec.py"],
    target = ":target_serial",
)

# A serial device in a container: the fake ECU answers on a TCP port. While compiling, the script's path is a
# stand-in; the test gets the built path.
itf_target(
    name = "target_serial_device",
    src = "targets/serial_device/serial_device.itf.yaml",
    srcs = ["targets/policy.py"],
    env = {"FAKE_ECU_SCRIPT": "targets/serial_device/fake_ecu.py"},
    packs = [
        "@score_itf//score/itf/packs/docker",
        "@score_itf//score/itf/packs/serial",
    ],
)

py_itf_test(
    name = "serial_device",
    srcs = ["test_exec.py"],
    data = ["targets/serial_device/fake_ecu.py"],
    env = {"FAKE_ECU_SCRIPT": "$(rootpath targets/serial_device/fake_ecu.py)"},
    target = ":target_serial_device",
)
