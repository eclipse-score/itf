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

# Starter: a Docker container from an image. Copy this folder and change the values marked `# CHANGE:`.
#
# Two kinds of file say what the target is made of: the target file (targets/target.itf.yaml) is its structure;
# an override file (targets/override.itf.yaml) holds only what differs in one setup and is merged over the target file
# by role. `bazel build :target` compiles it and writes target.plan.json: the roles, the wiring
# and the ordered actions, before anything exists.

DOCKER = "@score_itf//score/itf/packs/docker"

itf_target(
    name = "target",
    src = "targets/target.itf.yaml",
    srcs = ["targets/policy.py"],
    # CHANGE: the packs the factory labels name (`docker.platform` names `docker`).
    packs = [DOCKER],
)

# The same target file with the override file.
itf_target(
    name = "target_override",
    src = "targets/target.itf.yaml",
    srcs = ["targets/policy.py"],
    overrides = ["targets/override.itf.yaml"],
    packs = [DOCKER],
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
