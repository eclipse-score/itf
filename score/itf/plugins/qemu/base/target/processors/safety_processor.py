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
from score.itf.plugins.qemu.base.os.operating_system import OperatingSystem
from score.itf.plugins.qemu.base.target.config.base_processor import BaseProcessor
from score.itf.plugins.qemu.base.target.processors.target_processor import TargetProcessor


class TargetSafetyProcessor(TargetProcessor):
    """Represents the Safety processor of the target ECU."""

    # pylint: disable=useless-super-delegation
    def __init__(self, processor: BaseProcessor, os: OperatingSystem, diagnostic_ip=None):
        super().__init__(processor, os, diagnostic_ip)
