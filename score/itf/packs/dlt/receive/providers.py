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
"""dlt-receive providers. Constructing one starts nothing: `dlt.start_receive` (steps.py) does."""

from collections.abc import Iterator
from score.itf.core import capability

from .capture import DltCapture, Endpoint, ReceiveConfig


@capability("observe.logs", label="receive")
def make_receive(config: ReceiveConfig) -> Iterator[DltCapture]:
    receive = DltCapture(config)
    try:
        yield receive
    finally:
        receive.close()


@capability("observe.logs", label="receive_tcp")
def make_receive_tcp(endpoint: Endpoint, config: ReceiveConfig) -> Iterator[DltCapture]:
    receive = DltCapture(config, endpoint)
    try:
        yield receive
    finally:
        receive.close()
