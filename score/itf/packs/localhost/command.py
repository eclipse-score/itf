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
"""One-shot commands on the host (`localhost.exec`), run by /bin/sh in the platform's directory."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from score.itf.core.process import ProcessWrapper

logger = logging.getLogger(__name__)


class Platform(Protocol):
    __contract__ = "platform.instance"

    root: Path | None


def _short(text: str, limit: int = 200) -> str:
    """One log line: the first `limit` characters, newlines shown as ⏎."""
    text = text.replace("\r", "").replace("\n", "⏎")
    return text if len(text) <= limit else text[:limit] + f"… ({len(text)} chars)"


class LocalExec:
    def __init__(self, platform: Platform):
        self.platform = platform

    def exec(self, command: str, timeout: float = 30.0) -> tuple[int, str]:
        """(exit code, stdout followed by stderr); never raises on a nonzero exit."""
        logger.debug("local exec: sending %s", command)
        code, stdout, stderr = ProcessWrapper.run("/bin/sh", ["-c", command], cwd=self.platform.root, timeout=timeout)
        output = stdout + stderr
        logger.debug("local exec: output %s", _short(output))
        logger.info("local exec: %s -> exit %s", command, code)
        return code, output
