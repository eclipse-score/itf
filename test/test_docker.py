# *******************************************************************************
# Copyright (c) 2025 Contributors to the Eclipse Foundation
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

import score.itf


def check_command_exec(target, message):
    exit_code, output = target.exec_run(f"echo -n {message}")
    return f"{message}" == output.decode()


def test_docker_runs_1(target):
    assert check_command_exec(target, "hello, world 1")


def test_docker_runs_2(target):
    assert check_command_exec(target, "hello, world 1")


@score.itf.plugins.core.requires_capabilities("exec")
def test_docker_runs_for_exec_capability(target):
    assert check_command_exec(target, "hello, world 1")


@score.itf.plugins.core.requires_capabilities("non-existing-capability")
def test_docker_skipped_for_non_existing_capability(target):
    assert False, "This test should have been skipped due to missing capability"
