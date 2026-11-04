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
"""Starter tests for a container: run a command, transfer a file."""

import logging
from typing import Protocol

import score.itf as itf

log = logging.getLogger("starter.container.test")


class Command(Protocol):
    __contract__ = "exec.command"

    def exec(self, command: str, /) -> tuple[int, bytes]: ...


class Upload(Protocol):
    __contract__ = "files.transfer"

    def upload(self, local: str, remote: str, /) -> None: ...


itf_requires = itf.requires("command", shape=Command)


def test_run_a_command(target):
    log.info("scenario: a command in the container returns exit 0 and its output")
    code, out = target.command.exec("echo hello-itf")
    log.info("verdict: exit %s, greeting present: %s", code, b"hello-itf" in out)
    assert code == 0
    assert b"hello-itf" in out


@itf.requires("files", shape=Upload)
def test_transfer_a_file(target, tmp_path):
    log.info("scenario: a file uploaded from the host is readable in the container")
    local = tmp_path / "hello.txt"
    local.write_text("itf-upload-ok\n")
    target.files.upload(str(local), "/tmp/hello.txt")
    code, out = target.command.exec("cat /tmp/hello.txt")
    log.info("verdict: exit %s, content intact: %s", code, b"itf-upload-ok" in out)
    assert code == 0
    assert b"itf-upload-ok" in out
