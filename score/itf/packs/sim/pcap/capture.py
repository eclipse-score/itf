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
"""An in-memory capture recording whatever the simulation hands it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CaptureConfig:
    interface: str = "eth0"


class SimCapture:
    interface: str
    running: bool

    def __init__(self, interface: str):
        self.interface = interface
        self.running = False
        self._packets: list = []

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def record(self, event) -> None:
        self._packets.append(event)

    def packets(self) -> list:
        return list(self._packets)
