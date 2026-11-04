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


class Console(Protocol):
    __contract__ = "exec.console"

    def open(self) -> None: ...
    def is_open(self) -> bool: ...


@state("console.open", label="open")
def open_console(console: Console) -> None:
    console.open()


@open_console.probe
def is_console_open(console: Console) -> bool:
    return console.is_open()
