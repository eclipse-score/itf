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
"""Find core files on a target with a command and copy them to the host (Linux and QNX layouts)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

LIST_CORES = (
    "(ls -1 /core* 2>/dev/null || true)"
    " && (ls -1 /opt/*/core* 2>/dev/null || true)"
    " && (ls -1 /root/core* 2>/dev/null || true)"
    " && (ls -1 /tmp/core* 2>/dev/null || true)"
    " && (ls -1 /data/*/core* 2>/dev/null || true)"
    " && (ls -1 /tmp/*.core /tmp/*.core.gz /var/*.core /var/*.core.gz 2>/dev/null || true)"
    " && (ls -1 /opt/*/*.core /opt/*/*.core.gz /root/*.core /root/*.core.gz"
    " /data/*/*.core /data/*/*.core.gz 2>/dev/null || true)"
)


class Command(Protocol):
    __contract__ = "exec.command"

    def exec(self, command: str, timeout: float = 30.0) -> tuple[int, bytes]: ...


class Transfer(Protocol):
    __contract__ = "files.transfer"

    def download(self, remote_path: str, local_path: str) -> None: ...


def extract_core_dumps(command: Command, files: Transfer, output_dir: str) -> list[str]:
    """Download every core file found, mirroring its target path under `output_dir`."""
    _, listing = command.exec(LIST_CORES)
    found = [line.strip() for line in listing.decode("utf-8", errors="replace").splitlines() if line.strip()]
    logger.info("Found %d core file(s): %s", len(found), found)
    extracted = []
    for remote in found:
        local = os.path.join(output_dir, remote.lstrip("/"))
        if not Path(local).resolve().is_relative_to(Path(output_dir).resolve()):
            logger.warning("Skipping path traversal attempt: %s", remote)
            continue
        try:
            os.makedirs(os.path.dirname(local), exist_ok=True)
            files.download(remote, local)
            extracted.append(local)
        except Exception:
            logger.warning("Failed to extract core dump %s", remote, exc_info=True)
    return extracted
