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
"""A line-oriented serial console (UART) over pyserial (`serial.console`). A reader thread keeps
every received line (bounded), so boot output printed before any test runs is still available."""

from __future__ import annotations

import itertools
import math
import re
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ConsoleConfig:
    device: str
    baudrate: int = 115200
    logfile: str | None = None
    buffer: int = 20000
    read_timeout: float = 0.2
    stop_timeout: float = 5.0


def open_serial(device: str, baudrate: int, read_timeout: float):
    import serial

    return serial.serial_for_url(device, baudrate=baudrate, timeout=read_timeout)


class SerialConsole:
    def __init__(
        self,
        device: str,
        *,
        baudrate: int = 115200,
        logfile: str | None = None,
        buffer: int = 20000,
        read_timeout: float = 0.2,
        stop_timeout: float = 5.0,
        opener: Callable | None = None,
    ):
        if not device or not device.strip():
            raise ValueError("device must name a serial port")
        if baudrate <= 0 or buffer <= 0:
            raise ValueError("baudrate and buffer must be positive")
        for name, value in (("read_timeout", read_timeout), ("stop_timeout", stop_timeout)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        self.device = device
        self.baudrate = baudrate
        self.logfile = logfile
        self.read_timeout = read_timeout
        self.stop_timeout = stop_timeout
        self._opener = opener or open_serial
        self._port = None
        self._log = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._error: Exception | None = None
        self._lines: deque[str] = deque(maxlen=buffer)
        self._count = 0
        self._cond = threading.Condition()
        self._markers = itertools.count(1)

    def open(self) -> None:
        if self.is_open():
            return
        self.close()
        port = self._opener(self.device, self.baudrate, self.read_timeout)
        if self.logfile:
            Path(self.logfile).parent.mkdir(parents=True, exist_ok=True)
            self._log = open(self.logfile, "a", encoding="utf-8")
        self._port = port
        self._error = None
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._read_loop, args=(port,), daemon=True, name=f"console:{self.device}"
        )
        self._thread.start()

    def _append(self, line: str) -> None:
        with self._cond:
            self._lines.append(line)
            self._count += 1
            self._cond.notify_all()
        if self._log is not None:
            self._log.write(f"[{datetime.now().isoformat(timespec='milliseconds')}] {line}\n")
            self._log.flush()

    def _read_loop(self, port) -> None:
        partial = b""
        try:
            while not self._stop.is_set():
                chunk = port.read(getattr(port, "in_waiting", 0) or 1)
                if not chunk:
                    continue
                *complete, partial = (partial + chunk).split(b"\n")
                for raw in complete:
                    self._append(raw.rstrip(b"\r").decode("utf-8", errors="replace"))
        except Exception as exc:
            self._error = exc
        finally:
            if partial.strip():
                self._append(partial.rstrip(b"\r").decode("utf-8", errors="replace"))
            with self._cond:
                self._cond.notify_all()

    def is_open(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and self._error is None

    def write(self, text: str) -> None:
        if not self.is_open():
            raise RuntimeError(f"console {self.device} is not open")
        self._port.write(f"{text}\n".encode())
        flush = getattr(self._port, "flush", None)
        if flush is not None:
            flush()

    def mark(self) -> int:
        """A cursor for `lines()`/`wait_for()`: only lines received after this call."""
        with self._cond:
            return self._count

    def _since(self, since: int) -> list[str]:
        dropped = self._count - len(self._lines)
        return list(self._lines)[max(since - dropped, 0) :]

    def lines(self, since: int = 0) -> list[str]:
        with self._cond:
            return self._since(since)

    def wait_for(
        self, pattern: str, timeout: float = 30.0, *, since: int | None = None, regex: bool = False
    ) -> str | None:
        """The first matching line received after `since` (default: now), or None on timeout."""
        matches = re.compile(pattern).search if regex else (lambda line: pattern in line)
        cursor = self.mark() if since is None else since
        deadline = time.monotonic() + timeout
        with self._cond:
            while True:
                for line in self._since(cursor):
                    if matches(line):
                        return line
                cursor = max(cursor, self._count)
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not self.is_open():
                    return None
                self._cond.wait(remaining)

    def run(self, command: str, timeout: float = 30.0) -> tuple[int, str]:
        """Run a shell command on the console; return (exit code, output without echo/marker)."""
        marker = f"ITF_DONE_{next(self._markers)}"
        start = self.mark()
        # The marker starts a line of its own, so output without a trailing newline (echo -n) is kept; the
        # echoed command line still carries "%s", not the status, and is filtered with the marker.
        self.write(f"{command}; printf '\\n{marker}=%s\\n' $?")
        done = self.wait_for(rf"{marker}=(\d+)", timeout, since=start, regex=True)
        if done is None:
            raise TimeoutError(f"{command!r} did not finish on {self.device} within {timeout}s")
        code = int(re.search(rf"{marker}=(\d+)", done).group(1))
        output = [line for line in self.lines(start) if marker not in line]
        return code, "\n".join(output).strip()

    def close(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        try:
            if thread is not None:
                thread.join(timeout=self.stop_timeout)
        finally:
            port, self._port = self._port, None
            if port is not None:
                port.close()
            log, self._log = self._log, None
            if log is not None:
                log.close()
        if thread is not None and thread.is_alive():
            raise RuntimeError(f"console reader for {self.device} did not stop within {self.stop_timeout}s")
