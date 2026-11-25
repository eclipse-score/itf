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
"""File transfer through the Docker archive API (`docker.files`)."""

from __future__ import annotations

import logging

import io
import os
import tarfile

from .command import Platform

logger = logging.getLogger(__name__)


def download(container, remote_path: str, local_path: str) -> None:
    stream, _ = container.get_archive(remote_path)
    with tarfile.open(fileobj=io.BytesIO(b"".join(stream)), mode="r:*") as tar:
        members = tar.getmembers()
        if not members:
            raise FileNotFoundError(remote_path)
        if len(members) != 1 or not members[0].isfile():
            raise IsADirectoryError(f"Docker file download requires one regular file: {remote_path}")
        extracted = tar.extractfile(members[0])
        if extracted is None:
            raise FileNotFoundError(remote_path)
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(extracted.read())


class DockerFiles:
    """`files` through the Docker archive API: works with any image."""

    def __init__(self, platform: Platform):
        self.platform = platform

    def __enter__(self) -> DockerFiles:
        # Match SFTP's context-manager API without opening a persistent transfer channel.
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # The platform owns the container; leave it running and propagate transfer errors.
        return False

    def upload(self, local_path: str, remote_path: str) -> None:
        logger.info("docker upload: %s -> %s", local_path, remote_path)
        if not os.path.isfile(local_path):
            raise FileNotFoundError(local_path)
        remote_dir = os.path.dirname(remote_path) or "/"
        code, output = self.platform.container.exec_run(["mkdir", "-p", remote_dir])
        if code != 0:
            raise RuntimeError(f"Could not create remote path: {remote_dir}: {output!r}")
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w", dereference=True) as tar:
            tar.add(local_path, arcname=os.path.basename(remote_path))
        if not self.platform.container.put_archive(remote_dir, buffer.getvalue()):
            raise RuntimeError(f"Failed to upload '{local_path}' to '{remote_path}'")

    def download(self, remote_path: str, local_path: str) -> None:
        logger.info("docker download: %s -> %s", remote_path, local_path)
        download(self.platform.container, remote_path, local_path)
