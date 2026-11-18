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
"""Command-execution checks that run unchanged on any target that has a `command`.

Each test says what it expects and what the target answered, so the run log alone tells the story:
the scenario, the command sent (the provider logs it too), the answer, and the verdict.
"""

import logging
from typing import Protocol

import score.itf as itf

log = logging.getLogger("exec_everywhere.test")


class Command(Protocol):
    __contract__ = "exec.command"

    def exec(self, command: str, /) -> tuple[int, bytes]: ...


class Upload(Protocol):
    __contract__ = "files.transfer"

    def upload(self, local: str, remote: str, /) -> None: ...


class RecordedConsole(Protocol):
    __contract__ = "exec.console"

    def lines(self) -> list[str]: ...


@itf.requires("command", shape=Command)
def test_command_output_and_exit_code(target):
    log.info("scenario: a successful command returns exit 0 and its stdout")
    code, out = target.command.exec("echo hello-itf")
    log.info("verdict: exit %s, stdout contains the greeting: %s", code, b"hello-itf" in out)
    assert code == 0, "a successful command must exit 0"
    assert b"hello-itf" in out, "the command's stdout must be returned"


@itf.requires("command", shape=Command)
def test_stderr_is_part_of_the_output(target):
    log.info("scenario: text written to stderr comes back in the output")
    code, out = target.command.exec("sh -c 'echo to-stderr 1>&2'")
    log.info("verdict: exit %s, stderr text present: %s", code, b"to-stderr" in out)
    assert code == 0
    assert b"to-stderr" in out, "stderr must be part of the returned output"


@itf.requires("command", shape=Command)
def test_failing_command_reports_exit_code_without_raising(target):
    log.info("scenario: a failing command reports its exit code (3) instead of raising")
    code, _ = target.command.exec("sh -c 'exit 3'")
    log.info("verdict: exit code %s", code)
    assert code == 3, "a failing command must report its exit code"


@itf.requires("command", shape=Command)
@itf.requires("files", shape=Upload)
def test_uploaded_file_is_readable_by_a_command(target, tmp_path):
    log.info("scenario: a file uploaded from the host is readable on the target with a command")
    local = tmp_path / "payload.txt"
    local.write_text("itf-upload-ok\n")
    log.info("step: upload %s to /tmp/payload.txt", local.name)
    target.files.upload(str(local), "/tmp/payload.txt")
    log.info("step: read it back with a command")
    code, out = target.command.exec("cat /tmp/payload.txt")
    log.info("verdict: exit %s, content intact: %s", code, b"itf-upload-ok" in out)
    assert code == 0
    assert b"itf-upload-ok" in out, "uploaded content must be readable with a command"


@itf.requires("console", shape=RecordedConsole)
def test_console_recorded_the_boot_output(target):
    log.info("scenario: the console recorded output from before the first test")
    lines = target.console.lines()
    log.info("verdict: %d recorded line(s), first: %s", len(lines), lines[:1])
    assert lines, "the console recorded nothing since it opened"
