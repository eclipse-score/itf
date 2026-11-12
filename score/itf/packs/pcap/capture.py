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
"""A tcpdump subprocess writing a pcap file (`tcpdump.capture`), plus bounded per-test windows.
Capturing needs CAP_NET_RAW (or root) on the host: a host prerequisite, like the interface itself."""

from __future__ import annotations

import os
import shlex
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from score.itf.core.process import ProcessWrapper


def bundled(name: str) -> str:
    """A binary Bazel ships beside this module, or `name` itself to search PATH."""
    try:
        from python.runfiles import runfiles
    except ImportError:
        return name
    files = runfiles.Create()
    located = files.Rlocation(f"score_itf/score/itf/packs/pcap/{name}") if files else None
    return located if located and os.path.exists(located) else name


def default_out_dir() -> str:
    outputs = os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR")
    return os.path.join(outputs, "pcap") if outputs else "artifacts/pcap"


@dataclass(frozen=True)
class CaptureConfig:
    interface: str
    out_dir: str | None = None
    filter: str | None = None
    binary_path: str | None = None
    name: str | None = None


class TcpdumpCapture:
    def __init__(self, config: dict):
        self.interface = config["interface"]
        self.out_dir = Path(config.get("out_dir") or default_out_dir())
        self.filter = config.get("filter")
        self.binary_path = config.get("binary_path") or bundled("tcpdump")
        self.name = config.get("name") or self.interface
        self._process: ProcessWrapper | None = None
        self._out_file: Path | None = None

    def _command(self, out: Path, *, window: bool = False) -> list[str]:
        # immediate mode: a short window would otherwise lose libpcap's pending block on SIGTERM
        cmd = [self.binary_path, *(["--immediate-mode", "-U"] if window else []), "-i", self.interface, "-w", str(out)]
        return cmd + (shlex.split(self.filter) if self.filter else [])

    def start(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._out_file = self.out_dir / f"{self.name}.pcap"
        command = self._command(self._out_file)
        process = ProcessWrapper(command[0], command[1:], logger_name="tcpdump")
        process.start_process()
        self._process = process

    def stop(self) -> None:
        if self._process is not None:
            self._process.kill_process()
            self._process = None

    def running(self) -> bool:
        return self._process is not None and self._process.is_running()

    def path(self) -> Path:
        return self._out_file

    @contextmanager
    def window(self, name: str, *, ready_timeout: float = 5.0) -> Iterator[Path]:
        """A second tcpdump, bounded by the `with` block, beside the session-long capture."""
        out = self.out_dir / f"{name}.pcap"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.unlink(missing_ok=True)
        command = self._command(out, window=True)
        process = ProcessWrapper(command[0], command[1:], logger_name="tcpdump", keep_output=True)
        process.start_process()
        # tcpdump creates the file once the interface is open: only then is the window live
        deadline = time.monotonic() + ready_timeout
        while not out.exists() and process.is_running() and time.monotonic() < deadline:
            time.sleep(0.02)
        if not process.is_running() or not out.exists():
            process.kill_process()
            raise RuntimeError(f"capture window {name!r} on {self.interface} did not start: {process.output().strip()}")
        try:
            yield out
        finally:
            process.kill_process()
