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
"""The project's own code, shared by the four target files: readiness checks, evidence, and the one action
that is not in a pack, opening the fake ECU's console once the device answers. The target file is configured
(`py_itf_test(target = ...)`), not loaded here."""

import logging
import os
import socket
import time
from pathlib import Path
from typing import Protocol

from score.itf.core import hookimpl, state


log = logging.getLogger("exec_everywhere")
EVIDENCE = Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", ".")) / "evidence"


@hookimpl
def itf_verify(session):
    """Readiness, checked once after bring-up and before the first test: a target that cannot run a
    command, or whose console recorded nothing, fails here with a named check instead of in a test."""
    target = session.target
    log.info("verify: target offers %s", ", ".join(sorted(target.names())))
    if target.has("console"):
        # Before sending anything: a console that recorded no boot output at all has a problem of its own.
        first = target.console.wait_for("", timeout=10, since=0)
        session.check("console.recorded_boot", first is not None, detail=f"first recorded line: {first!r}")
    code, output = target.command.exec("echo -n ready")
    # endswith, not ==: a console may deliver its boot banner into the first command's output window
    session.check(
        "command.answers", code == 0 and output.strip().endswith(b"ready"), detail=f"exit {code}, output {output!r}"
    )
    if target.has("platform"):
        session.check("platform.running", target.platform.running())


@hookimpl
def itf_teardown(session):
    """Evidence, collected while the target still runs and before it is dismantled: what a person
    needs to follow what the target did (the console transcript)."""
    target = session.target
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if target.has("console"):
        path = EVIDENCE / "console.txt"
        path.write_text("\n".join(target.console.lines()), encoding="utf-8")
        log.info("teardown: console transcript (%d lines) saved to %s", len(target.console.lines()), path)


class Endpoint(Protocol):
    __contract__ = "descriptor.endpoint"  # the contract this file's own Protocol describes

    host: str
    port: int


class Console(Protocol):
    __contract__ = "exec.console"

    def open(self) -> None: ...
    def is_open(self) -> bool: ...


def _accepts_connections(endpoint: Endpoint) -> bool:
    """The device is up when it greets: a published port can accept a connection (the engine's forwarder)
    before anything inside the container listens, so a bare connect is not evidence."""
    try:
        with socket.create_connection((endpoint.host, endpoint.port), timeout=1) as connection:
            connection.settimeout(2)
            return connection.recv(1) != b""
    except OSError:
        return False


@state("console.open", after=("platform.up",), label="open_when_ecu_answers")
def open_when_ecu_answers(endpoint: Endpoint, console: Console) -> None:
    """Opens the console, but only once the device greets: it can take a moment after the container starts."""
    deadline = time.monotonic() + 60
    while not _accepts_connections(endpoint):
        if time.monotonic() > deadline:
            raise TimeoutError(f"{endpoint.host}:{endpoint.port} did not accept connections within 60 s")
        time.sleep(0.5)
    console.open()


@open_when_ecu_answers.probe
def console_is_open(endpoint: Endpoint, console: Console) -> bool:
    return console.is_open()
