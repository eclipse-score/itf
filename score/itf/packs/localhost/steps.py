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
from typing import Protocol

from score.itf.core import state


class Platform(Protocol):
    __contract__ = "platform.instance"

    def start(self) -> None: ...
    def running(self) -> bool: ...


@state("platform.up", label="start")
def start_platform(platform: Platform) -> None:
    platform.start()


@start_platform.probe
def platform_is_up(platform: Platform) -> bool:
    return platform.running()
