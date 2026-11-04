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
"""A capability whose factory starts a host process and never stops it: what a session must reap."""

from typing import Protocol

from score.itf.core import capability
from score.itf.core.process import ProcessWrapper


class Leak:
    def __init__(self, wrapper: ProcessWrapper):
        self.wrapper = wrapper

    @property
    def pid(self) -> int:
        return self.wrapper.pid


class LeakContract(Protocol):
    __contract__ = "leak.process"

    def pid(self): ...


@capability("leak.process", label="leaky")
def make_leak() -> Leak:
    return Leak(ProcessWrapper("sleep", ["30"]).start_process())
