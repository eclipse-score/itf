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
"""File transfer on the host (`localhost.files`): copies, creating directories."""

from __future__ import annotations

import logging

import os
import shutil
from typing import Protocol

logger = logging.getLogger(__name__)


class Platform(Protocol):
    __contract__ = "platform.instance"

    is_local: bool


class LocalFiles:
    def __init__(self, platform: Platform):
        self.platform = platform

    def upload(self, local_path: str, remote_path: str) -> None:
        logger.info("local upload: %s -> %s", local_path, remote_path)
        if not os.path.isfile(local_path):
            raise FileNotFoundError(local_path)
        os.makedirs(os.path.dirname(remote_path) or ".", exist_ok=True)
        shutil.copyfile(local_path, remote_path)

    def download(self, remote_path: str, local_path: str) -> None:
        logger.info("local download: %s -> %s", remote_path, local_path)
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        shutil.copyfile(remote_path, local_path)
