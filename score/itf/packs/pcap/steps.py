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
"""Capture on an interface that exists once the platform runs (a container's or VM's bridge)."""

from typing import Protocol

from score.itf.core import state


class Capture(Protocol):
    __contract__ = "observe.capture"

    def start(self) -> None: ...
    def running(self) -> bool: ...


@state("capture.running", label="start")
def start_capture(capture: Capture) -> None:
    capture.start()


@start_capture.probe
def is_capture_running(capture: Capture) -> bool:
    return capture.running()
