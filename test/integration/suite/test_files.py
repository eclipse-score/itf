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
from uuid import uuid4
import shlex

import pytest

import score.itf as itf


class Upload(Protocol):
    __contract__ = "files.transfer"

    def upload(self, local_path: str, remote_path: str, /) -> None: ...


class Download(Protocol):
    __contract__ = "files.transfer"

    def download(self, remote_path: str, local_path: str, /) -> None: ...


class FileContext(Protocol):
    __contract__ = "files.transfer"

    def __enter__(self): ...
    def __exit__(self, exc_type, exc_val, exc_tb): ...


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
@itf.requires("command", shape=Command)
@pytest.mark.parametrize("local_path", ["back.txt", "nested output/back.txt"])
def test_upload_then_download_round_trips(target, tmp_path, monkeypatch, local_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src.txt").write_text("hello from host\n", encoding="utf-8")
    remote_dir = f"/tmp/itf-upload-{uuid4().hex}"
    remote_path = f"{remote_dir}/nested folder's;$name/upload.txt"
    try:
        target.files.upload(str(tmp_path / "src.txt"), remote_path)
        target.files.download(remote_path, local_path)
        assert (tmp_path / local_path).read_text(encoding="utf-8") == "hello from host\n"
    finally:
        target.command.exec(f"rm -rf {shlex.quote(remote_dir)}")


def test_upload_rejects_a_missing_local_file(target, tmp_path):
    with pytest.raises(FileNotFoundError):
        target.files.upload(str(tmp_path / "missing"), f"/tmp/itf-missing-{uuid4().hex}")


@itf.requires("files", shape=Download)
@itf.requires("files", shape=FileContext)
@itf.requires("command", shape=Command)
def test_file_transfer_context_preserves_provider_usability(target, tmp_path):
    source = tmp_path / "source.txt"
    source.write_bytes(b"context-managed transfer\n")
    remote = f"/tmp/itf-context-{uuid4().hex}.txt"
    try:
        with target.files as files:
            assert files is target.files
            files.upload(str(source), remote)
            files.download(remote, str(tmp_path / "inside.txt"))
        target.files.download(remote, str(tmp_path / "after.txt"))
        assert (tmp_path / "inside.txt").read_bytes() == source.read_bytes()
        assert (tmp_path / "after.txt").read_bytes() == source.read_bytes()
    finally:
        target.command.exec(f"rm -f {remote}")


@itf.requires("command", shape=Command)
def test_an_uploaded_file_is_visible_to_commands(target, tmp_path):
    (tmp_path / "f.txt").write_text("visible\n", encoding="utf-8")
    remote_path = f"/tmp/itf-visible-{uuid4().hex}.txt"
    try:
        target.files.upload(str(tmp_path / "f.txt"), remote_path)
        assert target.command.exec(f"cat {remote_path}") == (0, b"visible\n")
    finally:
        target.command.exec(f"rm -f {remote_path}")


@itf.requires("files", shape=FileManagement)
def test_remote_file_management(target, tmp_path):
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    filename = f"itf-managed-{uuid4().hex}.txt"
    remote_path = f"/tmp/{filename}"
    try:
        target.files.upload(str(tmp_path / "f.txt"), remote_path)
        assert target.files.exists(remote_path)
        assert filename in target.files.listdir("/tmp")
        target.files.remove(remote_path)
        assert not target.files.exists(remote_path)
    finally:
        if target.files.exists(remote_path):
            target.files.remove(remote_path)
