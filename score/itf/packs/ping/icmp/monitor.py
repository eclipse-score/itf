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
"""Configurable endpoint reachability and waiting for boot or loss of connectivity."""

from __future__ import annotations

import ipaddress
import math
import re
import time
from dataclasses import dataclass

from . import probe
from ..ping import Endpoint, Ping


_HOSTNAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,252})$")


@dataclass(frozen=True)
class PingConfig:
    boot_timeout: float = 180.0
    interval: float = 1.0
    reply_timeout: float = 1.0
    binary_path: str = "ping"


def checked_host(host: str) -> str:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not _HOSTNAME.match(host):
            raise ValueError(f"invalid ping target {host!r}") from None
    return host


class Pinger(Ping):
    """`ping` for the endpoint's host."""

    host: str  # a property below; declared here so the class names its shape

    def __init__(self, endpoint: Endpoint, config: dict):
        self.endpoint = endpoint
        self.boot_timeout = config.get("boot_timeout", 180.0)
        self.interval = config.get("interval", 1.0)
        self.reply_timeout = config.get("reply_timeout", 1.0)
        self.binary_path = config.get("binary_path", "ping")
        for name in ("boot_timeout", "interval", "reply_timeout"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")

    @property
    def host(self) -> str:
        return checked_host(self.endpoint.host)

    def _probe(self, address, wait_ms_precision):
        timeout = self.reply_timeout if wait_ms_precision is None else wait_ms_precision
        return probe.ping(address, timeout, self.binary_path)

    def _wait(self, reachable: bool, timeout: float | None) -> bool:
        deadline = time.monotonic() + (self.boot_timeout if timeout is None else timeout)
        while True:
            if self.ping() == reachable:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(self.interval)

    def wait_up(self, timeout: float | None = None) -> bool:
        return self._wait(True, timeout)

    def wait_down(self, timeout: float | None = None) -> bool:
        return self._wait(False, timeout)
