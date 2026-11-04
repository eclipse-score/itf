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
"""The project's policy, shared by every integration target file: the dlt-daemon the DLT target files start
before they subscribe, and readiness checks, written against roles (`command`, `console`, `platform`, `process`).
The target file itself is configured (`ITF_TARGET`, or `py_itf_test(target = ...)`), not loaded here.
"""

import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from score.itf.core import capability, hookimpl, state

log = logging.getLogger("integration")
EVIDENCE = Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", ".")) / "evidence"


@hookimpl
def itf_verify(session):
    """Readiness, checked once after bring-up: a target that cannot answer fails here with a named check."""
    target = session.target
    log.info("verify: target offers %s", ", ".join(sorted(target.names())))
    if target.has("command"):
        code, output = target.command.exec("echo -n ready")
        session.check(
            "command.answers", code == 0 and output.strip().endswith(b"ready"), detail=f"exit {code}, {output!r}"
        )
    if target.has("platform"):
        session.check("platform.running", target.platform.running())


@hookimpl
def itf_teardown(session):
    """Evidence, collected while the target still runs: the console transcript."""
    target = session.target
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if target.has("console"):
        path = EVIDENCE / "console.txt"
        path.write_text("\n".join(target.console.lines()), encoding="utf-8")
        log.info("teardown: console transcript (%d lines) saved to %s", len(target.console.lines()), path)


class Process(Protocol):
    __contract__ = "exec.process"

    def spawn(self, binary_path: str, args: list[str] | None = None, cwd: str = "/"): ...


class DltDaemon:
    """dlt-daemon on the target. The handle of the program it spawned lives here, on the role."""

    def __init__(self, process: Process):
        self._process = process
        self._handle = None

    def start(self) -> None:
        self._handle = self._process.spawn("/usr/bin/dlt-daemon")

    def is_running(self) -> bool:
        return self._handle is not None and self._handle.is_running()

    def close(self) -> None:
        if self.is_running():
            self._handle.stop()


@capability("daemon.instance", label="dlt_daemon")
def make_dlt_daemon(process: Process) -> Iterator[DltDaemon]:
    daemon = DltDaemon(process)
    yield daemon
    daemon.close()


class Daemon(Protocol):
    __contract__ = "daemon.instance"

    def start(self) -> None: ...
    def is_running(self) -> bool: ...


@state("daemon.running", after=("platform.up",), label="start_dlt_daemon")
def start_dlt_daemon(daemon: Daemon) -> None:
    daemon.start()


@start_dlt_daemon.probe
def dlt_daemon_running(daemon: Daemon) -> bool:
    return daemon.is_running()
