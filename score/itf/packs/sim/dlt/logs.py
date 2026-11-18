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
"""An in-memory log stream fed by a simulated platform."""

from __future__ import annotations

from typing import Protocol


class EndpointLike(Protocol):
    __contract__ = "descriptor.endpoint"

    host: str
    port: int


class PlatformLike(Protocol):
    __contract__ = "platform.instance"

    gen: int
    log: list[str]


class LogStream:
    endpoint: EndpointLike
    platform: PlatformLike

    def __init__(self, endpoint: EndpointLike, platform: PlatformLike):
        self.endpoint = endpoint
        self.platform = platform
        self._subscribed = False
        self._gen = None

    def subscribe(self) -> None:
        self._subscribed = True
        self._gen = self.platform.gen

    def is_active(self) -> bool:
        return self._subscribed and self._gen == self.platform.gen

    def lines(self) -> list:
        if not self.is_active():
            self._subscribed = False
            raise RuntimeError("log stream is dead (platform was reimaged)")
        return list(self.platform.log)

    def close(self) -> None:
        self._subscribed = False
