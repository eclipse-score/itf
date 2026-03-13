# *******************************************************************************
# Copyright (c) 2025-2026 Contributors to the Eclipse Foundation
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
import os
import pytest

import score.itf


def check_command_exec(target, message):
    exit_code, output = target.execute(f"echo -n {message}")
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


def test_target_file_transfer_and_restart(target, tmp_path):
    local_src = tmp_path / "src.txt"
    local_dst = tmp_path / "dst.txt"
    remote_path = "/tmp/itf_upload_test.txt"

    content = "hello from host\n"
    local_src.write_text(content, encoding="utf-8")

    target.upload(str(local_src), remote_path)
    exit_code, output = target.execute(f"/bin/sh -c 'cat {remote_path}'")
    assert exit_code == 0
    assert output.decode() == content

    target.download(remote_path, str(local_dst))
    assert local_dst.read_text(encoding="utf-8") == content


def test_restart(target, tmp_path):
    target.restart()
    exit_code, output = target.execute("echo -n restarted")
    assert exit_code == 0
    assert output == b"restarted"


CONTAINER_EXTRA_MNT_PATH = "/extra/mount/directory"


@pytest.fixture(scope="session")
def docker_configuration():
    return {
        "volumes": {
            os.path.dirname(os.path.abspath(__file__)): {
                "bind": CONTAINER_EXTRA_MNT_PATH,
                "mode": "rw",
            }
        }
    }


def test_extra_mount(target):
    exit_code, _ = target.execute(f"ls -al {CONTAINER_EXTRA_MNT_PATH}")
    assert exit_code == 0, "Extra volume not mounted!"
