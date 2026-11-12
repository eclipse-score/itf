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
"""One-shot commands through the Docker exec API (`docker.exec`)."""

from __future__ import annotations

import logging

from typing import Protocol

logger = logging.getLogger(__name__)


class Platform(Protocol):
    __contract__ = "platform.instance"

    container: object

    def client(self): ...


def _short(text: str, limit: int = 200) -> str:
    """One log line: the first `limit` characters, newlines shown as ⏎."""
    text = text.replace("\r", "").replace("\n", "⏎")
    return text if len(text) <= limit else text[:limit] + f"… ({len(text)} chars)"


class DockerExec:
    """`command` through the Docker API: works with any image, no SSH needed.
    The Docker API has no exec timeout; `timeout` is accepted for the contract and not enforced."""

    def __init__(self, platform: Platform):
        self.platform = platform

    def exec(self, command: str, timeout: float = 30.0) -> tuple[int, bytes]:
        logger.debug("docker exec: sending %s", command)
        code, output = self.platform.container.exec_run(["/bin/sh", "-c", command])
        text = output.decode(errors="replace")
        logger.debug("docker exec: output %s", _short(text))
        logger.info("docker exec: %s -> exit %s", command, code)
        return code, output
