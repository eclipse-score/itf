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
"""The host as a platform (`local.instance`): a working directory created at start, removed at stop."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlatformConfig:
    root: str | None = None


MARKER = ".itf-local"


class LocalPlatform:
    """Nothing to boot: `start` creates the working directory commands run in.

    A configured `root` is found again by a later process: `start` leaves a marker file in it saying whether ITF
    created the directory, so `running` and `stop` work from a fresh instance. Without a `root` the directory
    is a temporary one that only this instance knows."""

    root: Path | None
    is_local: bool = True

    def __init__(self, config: dict):
        self._configured_root = config.get("root")
        self.root = Path(self._configured_root).absolute() if self._configured_root else None
        self._owned = False

    def start(self) -> None:
        if self._configured_root:
            created = not self.root.exists()
            self.root.mkdir(parents=True, exist_ok=True)
            (self.root / MARKER).write_text("created" if created else "existing", encoding="utf-8")
        else:
            self.root = Path(tempfile.mkdtemp(prefix="itf-local-"))
            self._owned = True

    def running(self) -> bool:
        if self._configured_root:
            return (self.root / MARKER).is_file()
        return self.root is not None and self.root.is_dir()

    def restart(self) -> None:
        """Nothing survives a host restart that matters here; the working directory stays."""

    def stop(self) -> None:
        if self._configured_root:
            marker = self.root / MARKER
            if marker.is_file():
                created = marker.read_text(encoding="utf-8") == "created"
                if created:
                    shutil.rmtree(self.root, ignore_errors=True)
                else:
                    marker.unlink()
            return
        if self._owned and self.root is not None:
            shutil.rmtree(self.root, ignore_errors=True)
        self.root = None
