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
"""`logs.active` for dlt-receive. It names no `after=`: what must run first (a daemon, a reachable target) is
said in the target file with `relations:`."""

from typing import Protocol

from score.itf.core import state


class Logs(Protocol):
    __contract__ = "observe.logs"

    def subscribe(self) -> None: ...
    def is_active(self) -> bool: ...


@state("logs.active", label="start_receive")
def start_receive(logs: Logs) -> None:
    logs.subscribe()


@start_receive.probe
def is_receiving(logs: Logs) -> bool:
    return logs.is_active()
