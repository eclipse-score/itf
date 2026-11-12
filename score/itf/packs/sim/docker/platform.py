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
"""An in-memory platform standing in for a container."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class PlatformConfig:
    name: str
    ip: str = "127.0.0.1"
    state_dir: str | None = None  # where "running" is remembered, so a later process can see it and take it down


class SimPlatform:
    """A fake machine: a file system dict, a command log, and a generation bumped by a reimage."""

    name: str
    ip: str
    running: bool
    fs: dict[str, str]
    gen: int
    log: list[str]

    def __init__(self, name: str, ip: str, state_dir: str | None = None):
        self.name = name
        self.ip = ip
        self._flag = Path(state_dir) / f"{name}.up" if state_dir else None
        self.running = self._flag is not None and self._flag.is_file()
        self.fs: dict[str, str] = {"/etc/version": "v0"}
        self.gen = 0
        self.log: list[str] = []

    def start(self) -> None:
        if self._flag is not None:
            self._flag.parent.mkdir(parents=True, exist_ok=True)
            self._flag.write_text("up", encoding="utf-8")
        self.running = True

    def stop(self) -> None:
        if self._flag is not None:
            self._flag.unlink(missing_ok=True)
        self.running = False

    def restart(self) -> None:
        self.gen += 1

    def exec(self, cmd: str) -> str:
        self.log.append(cmd)
        return f"ok:{cmd}"


class Platform(Protocol):
    __contract__ = "platform.instance"

    def exec(self, cmd: str) -> str: ...


class SimExec:
    def __init__(self, platform: Platform):
        self.platform = platform

    def exec(self, command: str, timeout: float = 30.0) -> tuple[int, bytes]:
        return 0, self.platform.exec(command).encode("utf-8")
