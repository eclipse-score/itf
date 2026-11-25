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
"""The original Docker plugin with --docker-ssh: files move over SFTP, and `target.ssh()` uses the target
file's endpoint and login."""

from uuid import uuid4

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


def test_file_transfers_round_trip_through_the_files_role(target, tmp_path):
    source = tmp_path / "source.txt"
    downloaded = tmp_path / "downloaded.txt"
    source.write_bytes(b"ITF file transfer round trip\n")
    remote = f"/tmp/itf-transfer-{uuid4().hex}"
    try:
        target.upload(str(source), remote)
        target.download(remote, str(downloaded))
        assert downloaded.read_bytes() == source.read_bytes()
    finally:
        target.execute(f"rm -f {remote}")


def test_ssh_uses_the_target_files_endpoint(target):
    with target.ssh() as ssh:
        exit_code, stdout, _ = ssh.execute_command_output("echo ok")
    assert exit_code == 0
    assert "".join(stdout).strip() == "ok"
