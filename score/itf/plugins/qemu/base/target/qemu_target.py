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

from score.itf.plugins.qemu.base.os.operating_system import OperatingSystem
from score.itf.plugins.qemu.base.target.base_target import Target
from score.itf.plugins.qemu.base.target.config.ecu import Ecu
from score.itf.plugins.qemu.base.target.processors.qemu_processor import TargetProcessorQemu
from score.itf.plugins.qemu.qemu_process import QemuProcess as Qemu


class TargetQemu(Target):
    """Target for the Qemu."""

    def __init__(self, target_ecu: Ecu, target_sut_os: OperatingSystem = OperatingSystem.LINUX):
        super().__init__(target_ecu, target_sut_os)

    # pylint: disable=unused-argument
    def register_processors(self, process=None, initialize_serial_device=True, initialize_serial_logs=True):
        self.sut = TargetProcessorQemu(self.target_ecu.sut, self.target_sut_os, process)
        self.processors.append(self.sut)


@contextmanager
def qemu_target(target_config, test_config):
    """Context manager for QEMU target setup.

    Currently, only ITF tests against an already running Qemu instance is supported.
    """
    with Qemu(
        target_config.qemu_image_path, None, target_config.qemu_ram_size, target_config.qemu_num_cores
    ) if target_config.qemu_image_path else nullcontext() as qemu_process:
        target = TargetQemu(test_config.ecu, test_config.os)
        target.register_processors(qemu_process)
        yield target
        target.teardown()
