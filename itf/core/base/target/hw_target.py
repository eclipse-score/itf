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
from contextlib import contextmanager, nullcontext
from itf.core.base.target.base_target import Target


@contextmanager
def hw_target(target_config, test_config):
    """Context manager for hardware target setup.

    Currently, only ITF tests against an already running hardware instance is supported.
    """
    diagnostic_ip = None

    with nullcontext():
        target = Target(test_config.ecu, test_config.os, diagnostic_ip)
        target.register_processors()
        yield target
        target.teardown()
