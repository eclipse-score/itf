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
"""The VM serial port as a recorded console (`qemu.console`)."""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Protocol
from score.itf.core.process import PipeConsole


class ConsolePlatform(Protocol):
    __contract__ = "platform.instance"

    console: PipeConsole | None


class QemuConsole:
    """`console` on the VM's serial port. Recording starts at `open` (the
    console.open action) and follows the platform across restarts."""

    def __init__(self, platform: ConsolePlatform):
        self.platform = platform
        self._lines: list[str] = []
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def open(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._record, daemon=True)
        self._thread.start()

    def _record(self) -> None:
        while not self._stop.is_set():
            console = self.platform.console
            if console is None:
                time.sleep(0.1)
                continue
            try:
                line = console.readline(block=True, timeout=0.2)
            except Exception:
                continue
            if line is not None:
                with self._lock:
                    self._lines.append(line)

    def is_open(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None

    def write(self, text: str) -> None:
        if self.platform.console is None:
            raise RuntimeError("the QEMU console is not running")
        self.platform.console.write(text)

    def mark(self) -> int:
        with self._lock:
            return len(self._lines)

    def lines(self, since: int = 0) -> list[str]:
        with self._lock:
            return list(self._lines[since:])

    def wait_for(
        self, pattern: str, timeout: float = 30.0, *, since: int | None = None, regex: bool = False
    ) -> str | None:
        start = self.mark() if since is None else since
        deadline = time.monotonic() + timeout
        while True:
            for line in self.lines(start):
                if re.search(pattern, line) if regex else pattern in line:
                    return line
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.1)

    def run(self, command: str, timeout: float = 30.0) -> tuple[int, str]:
        marker = f"ITF_DONE_{os.urandom(4).hex()}"
        start = self.mark()
        self.write(f"{command}; printf '\\n{marker}=%s\\n' $?")
        line = self.wait_for(rf"{marker}=(\d+)", timeout, since=start, regex=True)
        if line is None:
            raise TimeoutError(f"console command did not finish within {timeout}s: {command}")
        output = [l for l in self.lines(start) if marker not in l and l.strip() != command.strip()]
        return int(re.search(rf"{marker}=(\d+)", line).group(1)), "\n".join(output)
