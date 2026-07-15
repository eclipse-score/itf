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


_SUPPORTED_ARCHITECTURES = {
    "x86_64": {
        "qemu_path": "/usr/bin/qemu-system-x86_64",
        "cpu": "Cascadelake-Server-v5",
        "network_device": "virtio-net-pci",
        "machine": "pc",
        "block_device": "virtio-blk-pci",
    },
    "aarch64": {
        "qemu_path": "/usr/bin/qemu-system-aarch64",
        "cpu": "cortex-a53",
        "network_device": "virtio-net-device",
        "machine": "virt,virtualization=true,gic-version=3",
        "block_device": "virtio-blk-device",
    },
}


class Qemu:
    """
    This class shall be used to start an qemu instance based on pre-configured Qemu parameters.
    """

    def __init__(
        self,
        path_to_image,
        ram,
        cores,
        architecture,
        network_adapters,
        port_forwarding,
        disk_image,
        kernel_cmdline,
    ):
        """Create a QEMU instance with the specified parameters.

        :param str path_to_image: The path to the Qemu image file.
        :param str ram: The amount of RAM to allocate to the QEMU instance.
        :param str cores: The number of CPU cores to allocate to the QEMU instance.
        :param str architecture: The CPU architecture to emulate (x86_64 or aarch64).
        :param list network_adapters: List of network adapter names.
        :param list port_forwarding: List of port forwarding configurations.
        :param str disk_image: Optional path to a qcow2 disk image.
        :param str kernel_cmdline: Optional kernel command line string.
        """
        if architecture not in _SUPPORTED_ARCHITECTURES:
            raise ValueError("architecture must be one of: " + ", ".join(sorted(_SUPPORTED_ARCHITECTURES)))
        self.__arch_config = _SUPPORTED_ARCHITECTURES[architecture]
        self.__path_to_image = path_to_image
        self.__ram = ram
        self.__cores = cores
        self.__network_adapters = network_adapters
        self.__port_forwarding = port_forwarding
        self.__disk_image = disk_image
        self.__kernel_cmdline = kernel_cmdline

        self.__check_qemu_is_installed()
        self.__find_available_kvm_support()
        self.__check_kvm_readable_when_necessary()

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
        qemu_path = self.__arch_config["qemu_path"]
        if not os.path.isfile(qemu_path):
            logger.fatal(f"Qemu is not installed under {qemu_path}")
            sys.exit(-1)

    def __find_available_kvm_support(self):
        self._accelerator_support = "kvm"
        with open("/proc/cpuinfo") as cpuinfo:
            cpu_options = str(cpuinfo.read())
            if "vmx" not in cpu_options and "svm" not in cpu_options:
                logger.error("No virtual capability on machine. We're using standard TCG accel on QEMU")
                self._accelerator_support = "tcg"

            if not os.path.exists("/dev/kvm"):
                logger.error("No KVM available. We're using standard TCG accel on QEMU")
                self._accelerator_support = "tcg"

    def __check_kvm_readable_when_necessary(self):
        if self._accelerator_support == "kvm":
            if not os.access("/dev/kvm", os.R_OK):
                logger.fatal(
                    "You dont have access rights to /dev/kvm. Consider adding yourself to kvm group. Aborting."
                )
                sys.exit(-1)

    def __build_qemu_command(self):
        # Use hardware virtualization if available
        accel = ["-enable-kvm"] if self._accelerator_support == "kvm" else ["-accel", "tcg"]

        return (
            [self.__arch_config["qemu_path"]]
            + accel
            + [
                "-smp",
                f"{self.__cores},maxcpus={self.__cores},cores={self.__cores}",
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
            + self.__network_devices_args()
            + self.__port_forwarding_args()
            + self.__kernel_args()
            + self.__disk_image_args()
        )

    def __kernel_args(self):
        if not self.__path_to_image:
            return []
        args = ["-kernel", self.__path_to_image]
        if self.__kernel_cmdline:
            args.extend(["-append", self.__kernel_cmdline])
        return args

    def __disk_image_args(self):
        if not self.__disk_image:
            return []
        return [
            "-device",
            f"{self.__arch_config['block_device']},drive=vd0",
            "-drive",
            f"if=none,format=qcow2,file={self.__disk_image},id=vd0",
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
