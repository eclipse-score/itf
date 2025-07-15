# *******************************************************************************
# Copyright (c) 2025 Contributors to the Eclipse Foundation
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
import logging

from contextlib import contextmanager, nullcontext
from itf.plugins.base.target.base_target import Target
from itf.plugins.dlt.dlt_receive import DltReceive, Protocol


logger = logging.getLogger(__name__)


@contextmanager
def hw_target(target_config, test_config):
    """Context manager for hardware target setup.

    Currently, only ITF tests against an already running hardware instance is supported.
    """
    diagnostic_ip = None

    with nullcontext():
        with DltReceive(
            target_ip=target_config.ip_address,
            protocol=Protocol.UDP,
            binary_path="./itf/plugins/dlt/dlt-receive",
        ):
            target = Target(test_config.ecu, test_config.os, diagnostic_ip)
            target.register_processors()
            yield target
            target.teardown()
