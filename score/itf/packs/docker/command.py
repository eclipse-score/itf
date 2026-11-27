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
    """`command` through the Docker API, managed by the Docker exec process handle."""

    def __init__(self, platform: Platform):
        self.platform = platform

    def exec(self, command: str, timeout: float = 30.0) -> tuple[int, bytes]:
        from .process import DockerProcess, _DockerProcessTimeout

        logger.debug("docker exec: sending %s", command)
        process = DockerProcess(self.platform).spawn("/bin/sh", ["-c", command])
        try:
            code = process.wait(timeout_s=timeout)
        except _DockerProcessTimeout as exc:
            try:
                process.stop()
            except Exception as stop_error:
                raise TimeoutError(
                    f"Docker command exceeded {timeout} seconds and could not be stopped: {stop_error}"
                ) from exc
            raise TimeoutError(f"Docker command did not finish within {timeout} seconds") from exc
        output = process.get_output_bytes()
        text = output.decode(errors="replace")
        logger.debug("docker exec: output %s", _short(text))
        logger.info("docker exec: %s -> exit %s", command, code)
        return code, output
