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
"""Any target that moves files (`files`): container archive API, SFTP, host."""

import score.itf as itf


@itf.requires("files")
def test_upload_then_download_round_trips(target, tmp_path):
    (tmp_path / "src.txt").write_text("hello from host\n", encoding="utf-8")
    target.files.upload(str(tmp_path / "src.txt"), "/tmp/itf_files/nested/upload.txt")
    target.files.download("/tmp/itf_files/nested/upload.txt", str(tmp_path / "back.txt"))
    assert (tmp_path / "back.txt").read_text(encoding="utf-8") == "hello from host\n"


@itf.requires("files")
@itf.requires("command")
def test_an_uploaded_file_is_visible_to_commands(target, tmp_path):
    (tmp_path / "f.txt").write_text("visible\n", encoding="utf-8")
    target.files.upload(str(tmp_path / "f.txt"), "/tmp/itf_files/visible.txt")
    assert target.command.exec("cat /tmp/itf_files/visible.txt") == (0, b"visible\n")


@itf.requires("files", shape=["exists", "remove", "listdir"])
def test_remote_file_management(target, tmp_path):
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    target.files.upload(str(tmp_path / "f.txt"), "/tmp/itf_files/managed.txt")
    assert target.files.exists("/tmp/itf_files/managed.txt")
    assert "managed.txt" in target.files.listdir("/tmp/itf_files")
    target.files.remove("/tmp/itf_files/managed.txt")
    assert not target.files.exists("/tmp/itf_files/managed.txt")
