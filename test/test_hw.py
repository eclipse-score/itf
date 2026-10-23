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
"""Tests for a physical (bare-metal) SSH target.

Run against a Raspberry Pi at 192.168.0.175 (or any SSH host)::

    python main.py \\
        -p score.itf.plugins.core -p score.itf.plugins.hw_ssh \\
        --hw-host=192.168.0.175 --hw-user=pi --hw-password=<pass> \\
        test/test_hw.py -s

Or via Bazel::

    bazel test //test:test_hw \\
        --test_arg=--hw-user=pi --test_arg=--hw-password=<pass> \\
        --test_output=all
"""
import score.itf


def test_list_tmp(target):
    """List /tmp on the target and assert the command succeeds."""
    exit_code, output = target.execute("ls -la /tmp")
    assert exit_code == 0
    listing = output.decode()
    print(listing)
    assert listing.strip(), "/tmp listing was empty"


@score.itf.plugins.core.requires_capabilities("ssh")
def test_list_tmp_via_ssh(target):
    """List /tmp using the lower-level SSH API (stdout lines separated from stderr)."""
    with target.ssh() as ssh:
        exit_code, stdout_lines, stderr_lines = ssh.execute_command_output(
            "ls -la /tmp",
            timeout=10,
            max_exec_time=30,
            verbose=False,
            separate_stderr=True,
        )
    assert exit_code == 0, f"ls /tmp failed: {''.join(stderr_lines)}"
    listing = "".join(stdout_lines)
    print(listing)
    assert listing.strip(), "/tmp listing was empty"
