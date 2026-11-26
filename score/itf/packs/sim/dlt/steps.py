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


class LogStream(Protocol):
    __contract__ = "observe.logs"

    def subscribe(self) -> None: ...
    def is_active(self) -> bool: ...


@state("logs.active", label="subscribe")
def subscribe_logs(logs: LogStream) -> None:
    logs.subscribe()


@subscribe_logs.probe
def is_stream_active(logs: LogStream) -> bool:
    return logs.is_active()
