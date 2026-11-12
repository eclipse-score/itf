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

from typing import Protocol

import score.itf as itf


class Upload(Protocol):
    __contract__ = "files.transfer"

    def upload(self, local_path: str, remote_path: str, /) -> None: ...


class Download(Protocol):
    __contract__ = "files.transfer"

    def download(self, remote_path: str, local_path: str, /) -> None: ...


class FileManagement(Protocol):
    __contract__ = "files.transfer"

    def exists(self, path: str, /) -> bool: ...
    def remove(self, path: str, /) -> None: ...
    def listdir(self, path: str, /) -> list[str]: ...


class Command(Protocol):
    __contract__ = "exec.command"

    def exec(self, command: str, /) -> tuple[int, bytes]: ...


itf_requires = [itf.requires("files", shape=Upload)]


@itf.requires("files", shape=Download)
def test_upload_then_download_round_trips(target, tmp_path):
    (tmp_path / "src.txt").write_text("hello from host\n", encoding="utf-8")
    target.files.upload(str(tmp_path / "src.txt"), "/tmp/itf_files/nested/upload.txt")
    target.files.download("/tmp/itf_files/nested/upload.txt", str(tmp_path / "back.txt"))
    assert (tmp_path / "back.txt").read_text(encoding="utf-8") == "hello from host\n"


@itf.requires("command", shape=Command)
def test_an_uploaded_file_is_visible_to_commands(target, tmp_path):
    (tmp_path / "f.txt").write_text("visible\n", encoding="utf-8")
    target.files.upload(str(tmp_path / "f.txt"), "/tmp/itf_files/visible.txt")
    assert target.command.exec("cat /tmp/itf_files/visible.txt") == (0, b"visible\n")


@itf.requires("files", shape=FileManagement)
def test_remote_file_management(target, tmp_path):
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    target.files.upload(str(tmp_path / "f.txt"), "/tmp/itf_files/managed.txt")
    assert target.files.exists("/tmp/itf_files/managed.txt")
    assert "managed.txt" in target.files.listdir("/tmp/itf_files")
    target.files.remove("/tmp/itf_files/managed.txt")
    assert not target.files.exists("/tmp/itf_files/managed.txt")
