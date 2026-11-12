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
"""Starter tests for a machine over SSH: run a command, use a shell session."""

import logging
from typing import Protocol

import score.itf as itf

log = logging.getLogger("starter.ssh.test")


class Command(Protocol):
    __contract__ = "exec.command"

    def exec(self, command: str, /) -> tuple[int, bytes]: ...


class Shell(Protocol):
    __contract__ = "exec.shell"

    def execute_command_output(self, command: str, /) -> tuple[int, list[str], list[str]]: ...
    def execute_command(self, command: str, /) -> int: ...


@itf.requires("command", shape=Command)
def test_run_a_command(target):
    log.info("scenario: a command over SSH returns exit 0 and its output")
    code, out = target.command.exec("echo hello-itf")
    log.info("verdict: exit %s, greeting present: %s", code, b"hello-itf" in out)
    assert code == 0
    assert b"hello-itf" in out


@itf.requires("shell", shape=Shell)
def test_use_the_shell(target):
    log.info("scenario: the shell session logs in as the configured user and reports exit codes")
    code, out, _ = target.shell.execute_command_output("whoami")
    log.info("verdict: exit %s, user %s", code, "".join(out).strip())
    assert code == 0
    assert "".join(out).strip() == "score"
    code = target.shell.execute_command("sh -c 'exit 3'")
    log.info("verdict: failing command exit code %s", code)
    assert code == 3, "a failing command must report its exit code"
