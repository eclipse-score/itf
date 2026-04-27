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

import pytest


@pytest.fixture(scope="session")
def docker_configuration():
    return {
        "environment": {
            "PASSWORD_ACCESS": "true",
            "USER_NAME": "score",
            "USER_PASSWORD": "score",
        },
        "command": None,
        "init": False,
    }


def check_command_exec(target, message):
    exit_code, output = target.execute(f"echo -n {message}")
    return f"{message}" == output.decode()


def test_docker_runs_1(target):
    assert check_command_exec(target, "hello, world 1")


def test_ssh_with_default_user(target):
    exit_code, output = target.execute("/bin/sh -c \"echo 'Username:' $USER && uname -a\"")
    assert exit_code == 0
    assert b"Username:" in output


def test_execute_command_output_separates_stdout_and_stderr(target):
    with target.ssh() as ssh:
        exit_code, stdout_lines, stderr_lines = ssh.execute_command_output(
            "echo out; echo err 1>&2; exit 7",
            timeout=10,
            max_exec_time=30,
            verbose=False,
            separate_stderr=True,
        )

    assert exit_code == 7
    assert "out" in "".join(stdout_lines)
    assert "err" in "".join(stderr_lines)


def test_execute_command_output_merges_stderr_into_stdout_when_requested(target):
    with target.ssh() as ssh:
        exit_code, stdout_lines, stderr_lines = ssh.execute_command_output(
            "echo out; echo err 1>&2; exit 7",
            timeout=10,
            max_exec_time=30,
            verbose=False,
            separate_stderr=False,
        )

    assert exit_code == 7
    assert stderr_lines == []
    joined = "".join(stdout_lines)
    assert "out" in joined
    assert "err" in joined


def test_execute_command_output_preserves_line_splitting(target):
    with target.ssh() as ssh:
        exit_code, stdout_lines, stderr_lines = ssh.execute_command_output(
            "printf 'a\\nb\\n'",
            timeout=10,
            max_exec_time=30,
            verbose=False,
            separate_stderr=True,
        )

    assert exit_code == 0
    assert stderr_lines == []
    assert stdout_lines == ["a\n", "b\n"]


def test_execute_command_output_returns_minus_one_on_timeout(target):
    with target.ssh() as ssh:
        exit_code, stdout_lines, stderr_lines = ssh.execute_command_output(
            "sleep 2; echo done",
            timeout=10,
            max_exec_time=1,
            verbose=False,
            separate_stderr=True,
        )

    assert exit_code == -1


def test_execute_command_output_captures_large_stdout(target):
    # Generate a sizeable amount of stdout without relying on external utilities
    # (works with busybox /bin/sh). Roughly 65 bytes per iteration => ~325KB.
    cmd = (
        "i=0; "
        "while [ $i -lt 5000 ]; do "
        "printf '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\\n'; "
        "i=$((i+1)); "
        "done"
    )

    with target.ssh() as ssh:
        exit_code, stdout_lines, stderr_lines = ssh.execute_command_output(
            cmd,
            timeout=10,
            max_exec_time=30,
            verbose=False,
            separate_stderr=True,
        )

    assert exit_code == 0
    assert stderr_lines == []
    stdout = "".join(stdout_lines)
    assert len(stdout) > 300_000
