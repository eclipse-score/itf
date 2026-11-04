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

# Starter: a machine reached over SSH. For the local demo it is a container running sshd; for a real machine
# see targets/target.itf.yaml. The target file is the structure; targets/override.itf.yaml holds what differs in
# one setup. targets/ holds everything ITF reads; the test and its fixtures stay here.

# CHANGE: the packs the factory labels name; drop docker for a real machine.
PACKS = [
    "@score_itf//score/itf/packs/docker",
    "@score_itf//score/itf/packs/net",
    "@score_itf//score/itf/packs/ssh",
]

# The demo container's own account, which the container is started with: not a secret. For a real machine, leave
# the login out of env: the build compiles ${SSH_PASSWORD} as a placeholder, and the test run takes it from the
# environment (bazel test --test_env=SSH_USER --test_env=SSH_PASSWORD) or, without Bazel, from targets/.env.
DEMO_LOGIN = {
    "SSH_PASSWORD": "score",
    "SSH_USER": "score",
}

itf_target(
    name = "target",
    src = "targets/target.itf.yaml",
    srcs = ["targets/policy.py"],
    env = DEMO_LOGIN,
    packs = PACKS,
)

itf_target(
    name = "target_override",
    src = "targets/target.itf.yaml",
    srcs = ["targets/policy.py"],
    env = DEMO_LOGIN,
    overrides = ["targets/override.itf.yaml"],
    packs = PACKS,
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

# exec_everywhere includes this target file.
exports_files(
    [
        "targets/policy.py",
        "targets/target.itf.yaml",
    ],
    visibility = ["//examples/exec_everywhere:__pkg__"],
)
