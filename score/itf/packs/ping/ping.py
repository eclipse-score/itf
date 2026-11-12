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
"""Ping wait helpers for a target address."""

import shutil
import time
from typing import Protocol

from score.itf.core.process import ProcessWrapper


def _execute_command(cmd):
    return ProcessWrapper.run("/bin/sh", ["-c", cmd])[0]


def _ping(address, wait_ms_precision=None):
    if shutil.which("ping") is None:
        raise RuntimeError(
            "The 'ping' utility is not installed on this system. "
            "Please install it (e.g. 'apt install iputils-ping' on Debian/Ubuntu systems)."
        )
    timeout_command = f"timeout {wait_ms_precision} " if wait_ms_precision else ""
    return _execute_command(f"{timeout_command}ping -c 1 -W 1 " + address) == 0


def _wait(address, timeout, interval, wait_ms_precision, lost, probe=None):
    probe = probe or _ping
    if timeout == 0:
        return probe(address, wait_ms_precision) != lost
    for _ in range(int(timeout / interval)):
        time.sleep(interval)
        if probe(address, wait_ms_precision) != lost:
            return True
    return False


def ping(address, timeout=0, interval=1, wait_ms_precision=None):
    return _wait(address, timeout, interval, wait_ms_precision, False)


def ping_lost(address, timeout=0, interval=1, wait_ms_precision=None):
    return _wait(address, timeout, interval, wait_ms_precision, True)


def check_ping_lost(address):
    assert ping_lost(address, timeout=60)


def check_ping(address):
    assert ping(address, timeout=60)


class Endpoint(Protocol):
    __contract__ = "descriptor.endpoint"

    host: str


class Ping:
    host: str

    def __init__(self, endpoint: Endpoint):
        self.endpoint = endpoint

    @property
    def host(self) -> str:
        return self.endpoint.host

    def _probe(self, address, wait_ms_precision):
        return _ping(address, wait_ms_precision)

    def ping(self, timeout=0, interval=1, wait_ms_precision=None):
        return _wait(self.host, timeout, interval, wait_ms_precision, False, self._probe)

    def ping_lost(self, timeout=0, interval=1, wait_ms_precision=None):
        return _wait(self.host, timeout, interval, wait_ms_precision, True, self._probe)

    def wait_up(self, timeout: float | None = None) -> bool:
        """Polls until the target answers; False on timeout (one probe without one)."""
        return self.ping(timeout=timeout or 0)

    def wait_down(self, timeout: float | None = None) -> bool:
        """Polls until the target stops answering; False on timeout (one probe without one)."""
        return self.ping_lost(timeout=timeout or 0)
