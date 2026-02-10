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
import subprocess

from score.itf.core.utils.process.console import PipeConsole
from score.itf.core.qemu.qemu import Qemu

logger = logging.getLogger(__name__)


class QemuProcess:
    def __init__(self, path_to_qemu_image, path_to_bootloader, available_ram, available_cores):
        self._path_to_qemu_image = path_to_qemu_image
        self._path_to_bootloader = path_to_bootloader
        self._available_ram = available_ram
        self._available_cores = available_cores
        self._qemu = Qemu(
            self._path_to_qemu_image, self._path_to_bootloader, self._available_ram, self._available_cores
        )
        self._console = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        logger.info("Starting Qemu...")
        logger.info(f"Using QEMU image: {self._path_to_qemu_image}")
        subprocess_params = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
        }
        # pylint: disable=too-many-function-args
        qemu_subprocess = self._qemu.start(subprocess_params)
        self._console = PipeConsole("QEMU", qemu_subprocess)
        return self

    def stop(self):
        logger.info("Stopping Qemu...")
        self._qemu.stop()

    def restart(self):
        self.stop()
        self.start()

    @property
    def console(self):
        return self._console
