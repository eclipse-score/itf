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
load("//:defs.bzl", "py_itf_test", "py_itf_unittest")

# The compatibility layer's own tests. ITF's tests from main run unchanged in ../legacy (tools/legacy_unchanged.py
# keeps that directory byte-identical to main); what the layer adds to the original API is tested here.

# The original module paths hold no logic: each only re-exports from score.itf.compat or a pack.
py_itf_unittest(
    name = "shims_test",
    srcs = ["check_shims.py"],
    data = [
        "//score/itf/core/com",
        "//score/itf/core/target",
        "//score/itf/core/utils",
        "//score/itf/plugins:core",
        "//score/itf/plugins:core_dump",
        "//score/itf/plugins:docker",
        "//score/itf/plugins/dlt",
        "//score/itf/plugins/qemu",
    ],
)

# The original target classes as a facade over the roles of a composed target, without a container.
py_itf_unittest(
    name = "layer_test",
    srcs = glob(["layer/*.py"]),
    deps = [
        "//score/itf/compat",
        "//score/itf/plugins/qemu",
    ],
)

py_itf_test(
    name = "test_docker_configuration",
    srcs = ["test_docker_configuration.py"],
    args = ["--docker-image=ubuntu:24.04"],
    plugins = ["//score/itf/plugins:docker_plugin"],
    tags = ["requires-docker"],
    target_compatible_with = ["@platforms//os:linux"],
)

py_itf_test(
    name = "test_docker_ssh",
    srcs = ["test_docker_ssh.py"],
    args = [
        "--docker-ssh",
        "--docker-image=linuxserver/openssh-server:version-10.2_p1-r0",
    ],
    plugins = ["//score/itf/plugins:docker_plugin"],
    tags = ["requires-docker"],
    target_compatible_with = ["@platforms//os:linux"],
)
