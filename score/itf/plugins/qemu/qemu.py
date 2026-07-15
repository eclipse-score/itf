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
import subprocess
import sys

logger = logging.getLogger(__name__)


_SUPPORTED_MACHINES = {
    "pc-x86_64": {
        "architecture": "x86_64",
        "cpu": "Cascadelake-Server-v5",
        "network_device": "virtio-net-pci",
        "machine": "pc",
        "block_device": "virtio-blk-pci",
    },
    "virt-aarch64": {
        "architecture": "aarch64",
        "cpu": "cortex-a53",
        "network_device": "virtio-net-device",
        "machine": "virt,virtualization=true,gic-version=3",
        "block_device": "virtio-blk-device",
    },
}


def _get_qemu_path(architecture):
    return f"/usr/bin/qemu-system-{architecture}"


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

        self.__check_qemu_is_installed()

        self._subprocess = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self, subprocess_params=None):
        logger.debug(self.__build_qemu_command())
        subprocess_args = {"args": self.__build_qemu_command()}
        if subprocess_params:
            subprocess_args.update(subprocess_params)
        self._subprocess = subprocess.Popen(**subprocess_args)
        return self._subprocess

    def stop(self):
        if self._subprocess.poll() is None:
            self._subprocess.terminate()
            self._subprocess.wait(2)
        if self._subprocess.poll() is None:
            self._subprocess.kill()
            self._subprocess.wait(2)
        ret = self._subprocess.returncode
        if ret != 0:
            raise Exception(f"QEMU process returned: {ret}")

    def __check_qemu_is_installed(self):
        qemu_path = _get_qemu_path(self.__arch_config["architecture"])
        if not os.path.isfile(qemu_path):
            logger.fatal(f"Qemu is not installed under {qemu_path}")
            sys.exit(-1)

    def _extra_qemu_args(self):
        """Override in subclasses to inject additional QEMU flags (e.g. ivshmem devices)."""
        return []

    def __build_qemu_command(self):
        return (
            [
                _get_qemu_path(self.__arch_config["architecture"]),
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
                "mon:stdio",  # Redirect serial output to console
                "-object",
                "rng-random,filename=/dev/urandom,id=rng0",  # Provide hardware random number generation
                "-device",
                "virtio-rng-pci,rng=rng0",  # Provide hardware random number generation
            ]
            + self._extra_qemu_args()
            + self.__network_devices_args()
            + self.__port_forwarding_args()
            + self.__kernel_args()
            + self.__rootfs_args()
        )

    def __kernel_args(self):
        if not self.__path_to_kernel_image:
            return []
        args = ["-kernel", self.__path_to_kernel_image]
        if self.__kernel_cmdline:
            args.extend(["-append", self.__kernel_cmdline])
        return args

    def __rootfs_args(self):
        if not self.__rootfs:
            return []
        return [
            "-device",
            f"{self.__arch_config['block_device']},drive=vd0",
            "-drive",
            f"if=none,format=qcow2,file={self.__rootfs},id=vd0",
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
