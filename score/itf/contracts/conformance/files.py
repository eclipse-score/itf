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
"""Conformance of the files area."""

import os
import tempfile
import uuid

from score.itf.contracts.conformance import check, expect

FILES = "files.transfer"


def _remote_dir() -> str:
    return f"/tmp/itf_conformance_{uuid.uuid4().hex[:8]}"


@check()
def upload_then_download_round_trips(node):
    with tempfile.TemporaryDirectory() as tmp:
        src, back = os.path.join(tmp, "src.txt"), os.path.join(tmp, "back.txt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write("hello from host\n")
        remote = f"{_remote_dir()}/nested folder's;$name/upload.txt"  # the directories do not exist yet
        node.upload(src, remote)
        node.download(remote, back)
        with open(back, encoding="utf-8") as handle:
            content = handle.read()
    expect(content == "hello from host\n", f"downloaded content is {content!r}, expected what was uploaded")


@check()
def downloading_creates_the_local_directory(node):
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.txt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write("x")
        remote = f"{_remote_dir()}/f.txt"
        node.upload(src, remote)
        back = os.path.join(tmp, "new", "dir", "back.txt")
        node.download(remote, back)
        expect(os.path.isfile(back), f"download did not create {back}")


@check(shape=("exists", "remove", "listdir"))
def remote_file_management(node):
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "f.txt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write("x")
        directory = _remote_dir()
        remote = f"{directory}/managed.txt"
        node.upload(src, remote)
        expect(node.exists(remote), f"exists({remote!r}) is false right after upload")
        expect("managed.txt" in node.listdir(directory), f"listdir({directory!r}) does not list managed.txt")
        node.remove(remote)
        expect(not node.exists(remote), f"exists({remote!r}) is still true after remove")


@check()
def uploading_a_missing_source_raises_file_not_found(node):
    with tempfile.TemporaryDirectory() as tmp:
        try:
            node.upload(os.path.join(tmp, "missing.txt"), f"{_remote_dir()}/missing.txt")
        except FileNotFoundError:
            return
    expect(False, "upload of a missing local file did not raise FileNotFoundError")


@check()
def contexts_preserve_identity_errors_and_reusability(node):
    with node as files:
        expect(files is node, "context entry must return the file provider itself")
        upload_then_download_round_trips(files)
    error = RuntimeError("file transfer context sentinel")
    try:
        with node:
            raise error
    except RuntimeError as caught:
        expect(caught is error, "context exit replaced the original exception")
    else:
        expect(False, "context exit suppressed an exception")
    upload_then_download_round_trips(node)


CHECKS = {
    FILES: [
        upload_then_download_round_trips,
        downloading_creates_the_local_directory,
        uploading_a_missing_source_raises_file_not_found,
        contexts_preserve_identity_errors_and_reusability,
        remote_file_management,
    ]
}
