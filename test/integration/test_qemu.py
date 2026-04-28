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

import os
import score.itf


def test_ssh_with_default_user(target):
    exit_code, _ = target.execute("echo 'Username:' $USER && uname -a")
    assert exit_code == 0


@score.itf.plugins.core.requires_capabilities("ssh")
def test_ssh_with_qnx_user(target):
    with target.ssh(username="qnxuser") as ssh:
        exit_code = ssh.execute_command("echo 'Username:' $USER && uname -a")
        assert exit_code == 0


@score.itf.plugins.core.requires_capabilities("file_transfer")
def test_upload_download(target, tmp_path):
    local_src = tmp_path / "src.txt"
    local_dst = tmp_path / "dst.txt"
    remote_path = "/tmp/itf_upload_test.txt"

    content = "hello from host\n"
    local_src.write_text(content, encoding="utf-8")

    target.upload(str(local_src), remote_path)
    exit_code, output = target.execute(f"cat {remote_path}")
    assert exit_code == 0
    assert output.decode("utf-8") == content

    target.download(remote_path, str(local_dst))
    assert local_dst.read_text(encoding="utf-8") == content

    target.execute(f"rm -f {remote_path}")


def _wait_for_target_up(target, *, timeout_s: int = 120) -> None:
    assert target.ping(timeout=timeout_s), "Target did not become pingable in time"
    with target.ssh(timeout=10, n_retries=max(1, int(timeout_s / 2)), retry_interval=2) as ssh:
        exit_code = ssh.execute_command("echo -n up")
        assert exit_code == 0


def test_restart(target):
    exit_code, output = target.execute("echo -n before restart")
    assert exit_code == 0
    assert output == b"before restart"

    target.restart()
    _wait_for_target_up(target)

    exit_code, output = target.execute("echo -n restarted")
    assert exit_code == 0
    assert output == b"restarted"
