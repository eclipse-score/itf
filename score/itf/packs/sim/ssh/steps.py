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
"""Opening a simulated session: nothing listens, so the platform's state stands in for reachability."""

from typing import Protocol

from score.itf.core import state


class Platform(Protocol):
    __contract__ = "platform.instance"

    running: bool


class Shell(Protocol):
    __contract__ = "exec.shell"

    platform: Platform

    def connect(self) -> None: ...
    def is_connected(self) -> bool: ...


@state("shell.open", also=("network.reachable",), label="open")
def open_session(shell: Shell) -> None:
    shell.connect()


@open_session.probe
def is_session_open(shell: Shell) -> bool:
    return shell.is_connected()


@open_session.probe_for("network.reachable")
def is_reachable(shell: Shell) -> bool:
    return shell.platform.running
