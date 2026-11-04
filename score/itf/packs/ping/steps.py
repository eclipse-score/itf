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
"""`platform.up` for a machine nobody here starts (hardware, an externally run VM): it is
up once its address answers ICMP echo. Load instead of a platform pack's start action, not beside it."""

from typing import Protocol

from score.itf.core import state


class Pinger(Protocol):
    __contract__ = "net.ping"

    host: str

    def ping(self) -> bool: ...
    def wait_up(self, timeout: float | None = None) -> bool: ...


@state("platform.up", label="await_boot")
def await_boot(ping: Pinger) -> None:
    if not ping.wait_up():
        raise TimeoutError(f"{ping.host} did not answer ICMP echo within its boot timeout")


@await_boot.probe
def is_answering(ping: Pinger) -> bool:
    return ping.ping()
