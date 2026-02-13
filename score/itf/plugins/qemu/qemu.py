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
import os
import shlex
import sys
import subprocess
import logging

logger = logging.getLogger(__name__)


class Qemu:
    """
    This class shall be used to start an qemu instance based on pre-configured Qemu parameters.
    """

    def __init__(
        self,
        path_to_image,
        ram="1G",
        cores="2",
        cpu="Cascadelake-Server-v5",
        network_adapters=[],
        port_forwarding=[],
    ):
        """Create a QEMU instance with the specified parameters.

        :param str path_to_image: The path to the Qemu image file.
        :param str ram: The amount of RAM to allocate to the QEMU instance.
        :param str cores: The number of CPU cores to allocate to the QEMU instance.
        :param str cpu: The CPU model to emulate.
         Default is Cascadelake-Server-v5 used to emulate modern Intel CPU features.
         For older Ubuntu versions change that to host in case of errors.
        """
        self.__qemu_path = "/usr/bin/qemu-system-x86_64"
        self.__path_to_image = path_to_image
        self.__ram = ram
        self.__cores = cores
        self.__cpu = cpu
        self.__network_adapters = network_adapters
        self.__port_forwarding = port_forwarding

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
        if not os.path.isfile(self.__qemu_path):
            logger.fatal(f"Qemu is not installed under {self.__qemu_path}")
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
        return (
            [
                f"{self.__qemu_path}",
                "--enable-kvm"
                if self._accelerator_support == "kvm"
                else " -accel tcg",  # Use hardware virtualization if available
                "-smp",
                f"{self.__cores},maxcpus={self.__cores},cores={self.__cores}",
                "-cpu",
                f"{self.__cpu}",  # Specify CPU to emulate
                "-m",
                f"{self.__ram}",  # Specify RAM size
                "-kernel",
                f"{self.__path_to_image}",  # Specify kernel image
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
        )

    def __network_devices_args(self):
        def get_netdev_args(adapter, id):
            return [
                "-netdev",
                f"tap,id=t{id},ifname={adapter},script=no,downscript=no",
                "-device",
                f"virtio-net-pci,netdev=t{id},id=nic{id},guest_csum=off",
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
                    f"virtio-net-pci,netdev=net{id}",
                ]
            )
        return result
