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
import os

from score.itf.core.process import ProcessWrapper

logger = logging.getLogger(__name__)


_SUPPORTED_MACHINES = {
    "pc-x86_64": {
        "architecture": "x86_64",
        "cpu": "Cascadelake-Server-v5",
        "network_device": "virtio-net-pci",
        "machine": "pc",
        "block_device": "virtio-blk-pci",
        # virtio-blk-pci is probed by the guest in the same order the devices are
        # specified on the command line.
        "block_device_order": "ascending",
    },
    "virt-aarch64": {
        "architecture": "aarch64",
        "cpu": "cortex-a53",
        "network_device": "virtio-net-device",
        "machine": "virt,virtualization=true,gic-version=3",
        "block_device": "virtio-blk-device",
        # virtio-blk-device (virtio-mmio) is probed by the guest in the reverse order
        # the devices are specified on the command line.
        "block_device_order": "descending",
    },
}


def _get_qemu_path(architecture, binary_dir="/usr/bin"):
    return os.path.join(binary_dir, f"qemu-system-{architecture}")


class Qemu:
    """
    This class shall be used to start an qemu instance based on pre-configured Qemu parameters.
    """

    def __init__(
        self,
        path_to_kernel_image,
        ram,
        cores,
        machine,
        network_adapters,
        port_forwarding,
        rootfs,
        kernel_cmdline,
        disk,
        binary_dir="/usr/bin",
        serial_backend="mon:stdio",
    ):
        """Create a QEMU instance with the specified parameters.

        :param str path_to_kernel_image: The path to the Qemu kernel image file.
        :param str ram: The amount of RAM to allocate to the QEMU instance.
        :param str cores: The number of CPU cores to allocate to the QEMU instance.
        :param str machine: The QEMU machine to emulate (pc-x86_64 or virt-aarch64). The CPU
            architecture and thus the QEMU binary is derived from the machine.
        :param list network_adapters: List of network adapter names.
        :param list port_forwarding: List of port forwarding configurations.
        :param str rootfs: Optional path to a qcow2 disk image.
        :param str kernel_cmdline: Optional kernel command line string.
        :param str disk: Optional path to an additional qcow2 disk image.
        """
        if machine not in _SUPPORTED_MACHINES:
            raise ValueError("machine must be one of: " + ", ".join(sorted(_SUPPORTED_MACHINES)))
        self.__arch_config = _SUPPORTED_MACHINES[machine]
        self.__path_to_kernel_image = path_to_kernel_image
        self.__ram = ram
        self.__cores = cores
        self.__network_adapters = network_adapters
        self.__port_forwarding = port_forwarding
        self.__rootfs = rootfs
        self.__kernel_cmdline = kernel_cmdline
        self.__disk = disk
        self.__binary = _get_qemu_path(self.__arch_config["architecture"], binary_dir)
        self.__serial_backend = serial_backend

        self._subprocess = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self, console_callbacks=None) -> ProcessWrapper:
        """Start QEMU as a tracked process whose stdin/stdout are the guest's console (`wrapper.console`);
        `console_callbacks` are (expression, callback) pairs watched from the console's first line."""
        self.__check_qemu_is_installed()
        command = self.__build_qemu_command()
        logger.debug(command)
        self._subprocess = ProcessWrapper(
            command[0], command[1:], logger_name="QEMU", console_callbacks=console_callbacks
        )
        self._subprocess.start_process()
        return self._subprocess

    def is_running(self) -> bool:
        return self._subprocess is not None and self._subprocess.is_running()

    def terminate(self) -> None:
        """Ask QEMU to end, without waiting (from the console's reader thread, for instance)."""
        if self._subprocess is not None:
            self._subprocess.terminate()

    def stop(self):
        if self._subprocess is None:
            return
        self._subprocess.kill_process()
        ret = self._subprocess.exit_code()
        if ret != 0:
            raise Exception(f"QEMU process returned: {ret}")

    def __check_qemu_is_installed(self):
        if not os.path.isfile(self.__binary):
            raise RuntimeError(f"QEMU is not installed: {self.__binary} is missing (a host prerequisite)")

    def _extra_qemu_args(self):
        """Override in subclasses to inject additional QEMU flags (e.g. ivshmem devices)."""
        return []

    def __build_qemu_command(self):
        return (
            [
                self.__binary,
                # Use hardware virtualization if available
                "-accel",
                "kvm",
                "-accel",
                "tcg",
                "-smp",
                f"{self.__cores},maxcpus={self.__cores},cores={self.__cores}",
                "-machine",
                self.__arch_config["machine"],
                "-cpu",
                self.__arch_config["cpu"],  # Specify CPU to emulate
                "-m",
                f"{self.__ram}",  # Specify RAM size
                "-nographic",  # Disable graphical display (console-only)
                "-serial",
                self.__serial_backend,
                "-object",
                "rng-random,filename=/dev/urandom,id=rng0",  # Provide hardware random number generation
                "-device",
                "virtio-rng-pci,rng=rng0",  # Provide hardware random number generation
            ]
            + self._extra_qemu_args()
            + self.__network_devices_args()
            + self.__port_forwarding_args()
            + self.__kernel_args()
            + self.__disks_args()
        )

    def __kernel_args(self) -> list[str]:
        if not self.__path_to_kernel_image:
            return []
        args = ["-kernel", self.__path_to_kernel_image]
        if self.__kernel_cmdline:
            args.extend(["-append", self.__kernel_cmdline])
        return args

    def __disks_args(self) -> list[str]:
        # Order the disks so that, regardless of the guest's probing order, the rootfs
        # always ends up as the first block device (/dev/vda) in the guest.
        disks = [self.__rootfs, self.__disk]
        if self.__arch_config["block_device_order"] == "descending":
            disks = list(reversed(disks))
        args = []
        for id, disk in enumerate(disks):
            args += self.__disk_args(disk, id)
        return args

    def __disk_args(self, disk: str, id: int) -> list[str]:
        if not disk:
            return []
        return [
            "-device",
            f"{self.__arch_config['block_device']},drive=vd{id}",
            "-drive",
            f"if=none,format=qcow2,file={disk},id=vd{id}",
        ]

    def __network_devices_args(self):
        def get_netdev_args(adapter, id):
            return [
                "-netdev",
                f"tap,id=t{id},ifname={adapter},script=no,downscript=no",
                "-device",
                f"{self.__arch_config['network_device']},netdev=t{id},id=nic{id},guest_csum=off",
            ]

        result = []
        for id, adapter in enumerate(self.__network_adapters, start=1):
            if not adapter.startswith("lo"):
                result.extend(get_netdev_args(adapter, id))
        return result

    def __port_forwarding_args(self):
        result = []
        for id, forwarding in enumerate(self.__port_forwarding, start=1):
            result.extend(
                [
                    "-netdev",
                    f"user,id=net{id},hostfwd=tcp::{forwarding.host_port}-:{forwarding.guest_port}",
                    "-device",
                    f"{self.__arch_config['network_device']},netdev=net{id}",
                ]
            )
        return result
