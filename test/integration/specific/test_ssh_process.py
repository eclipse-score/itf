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
"""Processes over SSH (`process` on the sshd container or the QNX machine): a program whose arguments hold
quoted shell metacharacters still replaces the shell, so the PID reported is the program's own."""

import time

import score.itf as itf


@itf.requires("process")
def test_the_pid_is_the_programs_own_with_quoted_metacharacters_in_the_arguments(target):
    process = target.process.spawn("/bin/sh", args=["-c", 'echo "$$"; exec sleep 30 # ;|'])
    try:
        deadline = time.monotonic() + 10
        while not process.get_output().strip() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert int(process.get_output().strip()) == process.pid()
    finally:
        process.stop()
