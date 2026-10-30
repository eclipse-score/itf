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
import threading

from score.itf.core.process.console import PipeConsole
from score.itf.plugins.qemu.qemu import Qemu

logger = logging.getLogger(__name__)

# Printed by the QNX kernel on a fatal kernel error, e.g.
# "Shutdown[1] S/C/F=5/4/3 ...". The guest does not recover afterwards.
GUEST_PANIC_MARKER = "Shutdown["


class QemuProcess:
    def __init__(
        self,
        path_to_qemu_kernel_image,
        available_ram,
        available_cores,
        network_adapters,
        port_forwarding,
        machine,
        rootfs,
        kernel_cmdline,
        disk,
    ):
        self._path_to_qemu_kernel_image = path_to_qemu_kernel_image
        self._available_ram = available_ram
        self._available_cores = available_cores
        self._network_adapters = network_adapters
        self._port_forwarding = port_forwarding
        self._machine = machine
        self._rootfs = rootfs
        self._kernel_cmdline = kernel_cmdline
        self._disk = disk
        self._qemu = Qemu(
            self._path_to_qemu_kernel_image,
            self._available_ram,
            self._available_cores,
            network_adapters=self._network_adapters,
            port_forwarding=self._port_forwarding,
            machine=self._machine,
            rootfs=self._rootfs,
            kernel_cmdline=self._kernel_cmdline,
            disk=self._disk,
        )
        self._console = None
        self._guest_panicked = threading.Event()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        logger.info("Starting Qemu...")
        if self._path_to_qemu_kernel_image is not None:
            logger.info(f"Using QEMU kernel image: {self._path_to_qemu_kernel_image}")
        if self._kernel_cmdline is not None:
            logger.info(f"Using QEMU kernel command line: {self._kernel_cmdline}")
        if self._rootfs is not None:
            logger.info(f"Using QEMU root filesystem image: {self._rootfs}")
        if self._disk is not None:
            logger.info(f"Using QEMU additional disk image: {self._disk}")
        subprocess_params = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
        }
        # pylint: disable=too-many-function-args
        self._guest_panicked.clear()
        qemu_subprocess = self._qemu.start(subprocess_params)
        self._console = PipeConsole(
            "QEMU",
            qemu_subprocess,
            expr_cbks=[(GUEST_PANIC_MARKER, lambda: self._on_guest_panic(qemu_subprocess))],
        )
        return self

    def _on_guest_panic(self, qemu_subprocess):
        logger.error("Guest kernel panic detected on the serial console")
        self._guest_panicked.set()
        # The halted guest never recovers. Terminating QEMU makes any pending SSH
        # connection fail immediately instead of waiting for a banner that never arrives.
        if qemu_subprocess.poll() is None:
            qemu_subprocess.terminate()

    @property
    def guest_panicked(self) -> bool:
        """True if the guest kernel reported a panic since the last (re)start."""
        return self._guest_panicked.is_set()

    def stop(self):
        logger.info("Stopping Qemu...")
        self._qemu.stop()

    def restart(self):
        self.stop()
        self.start()

    @property
    def console(self):
        return self._console
