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

from itf.core.utils.process.console import PipeConsole
from itf.core.qemu.qemu import Qemu
from itf.core.base.target.config.ecu import Ecu

logger = logging.getLogger(__name__)


class QemuProcess:

    def __init__(self, config: Ecu):

        self._path_to_qemu_image = config.qemu_image_path
        self._qemu = Qemu(config)
        self._console = None

    def __enter__(self) -> "QemuProcess":
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self) -> "QemuProcess":
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
    def console(self) -> PipeConsole:
        return self._console
