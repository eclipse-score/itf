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

# Starter: a serial console. For the local demo it is a shell on a pseudo-terminal (no hardware), the
# `serial.pty_console` factory. For a real device use `serial.console` and set `device` in the target file or in
# an override file.

SERIAL = "@score_itf//score/itf/packs/serial"

itf_target(
    name = "target",
    src = "targets/target.itf.yaml",
    srcs = ["targets/policy.py"],
    packs = [SERIAL],
)

itf_target(
    name = "target_override",
    src = "targets/target.itf.yaml",
    srcs = ["targets/policy.py"],
    overrides = ["targets/override.itf.yaml"],
    packs = [SERIAL],
)

py_itf_test(
    name = "test",
    srcs = ["test_hello.py"],
    target = ":target",
)

py_itf_test(
    name = "test_override",
    srcs = ["test_hello.py"],
    target = ":target_override",
)
