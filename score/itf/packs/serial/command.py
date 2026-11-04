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
"""One-shot commands typed on a console node (`serial.exec`)."""

from __future__ import annotations

import logging

from typing import Protocol

logger = logging.getLogger(__name__)


class ConsoleLike(Protocol):
    __contract__ = "exec.console"

    def run(self, command: str, timeout: float = 30.0) -> tuple[int, str]: ...


def _short(text: str, limit: int = 200) -> str:
    """One log line: the first `limit` characters, newlines shown as ⏎."""
    text = text.replace("\r", "").replace("\n", "⏎")
    return text if len(text) <= limit else text[:limit] + f"… ({len(text)} chars)"


class SerialExec:
    """`command` over a console node; the console owns the port."""

    def __init__(self, console: ConsoleLike):
        self.console = console

    def exec(self, command: str, timeout: float = 30.0) -> tuple[int, bytes]:
        logger.debug("serial exec: sending %s", command)
        code, output = self.console.run(command, timeout)
        logger.debug("serial exec: output %s", _short(output))
        logger.info("serial exec: %s -> exit %s", command, code)
        return code, output.encode("utf-8")
