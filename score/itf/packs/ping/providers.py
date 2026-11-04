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
"""ICMP ping provider."""

from score.itf.core import capability

from .icmp.monitor import Endpoint, PingConfig, Pinger
from .ping import Ping


@capability("net.ping", label="ping")
def make_ping(endpoint: Endpoint) -> Ping:
    return Ping(endpoint)


@capability("net.ping", label="pinger")
def make_pinger(endpoint: Endpoint, config: PingConfig) -> Pinger:
    return Pinger(endpoint, config)
