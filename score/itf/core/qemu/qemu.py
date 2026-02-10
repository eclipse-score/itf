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
import netifaces
import logging

logger = logging.getLogger(__name__)


class Qemu:
    """
    This class shall be used to start an qemu instance based on pre-configured Qemu parameters.
    """

    def __init__(
        self,
        path_to_image,
        path_to_bootloader=None,
        ram="1G",
        cores="2",
        cpu="Cascadelake-Server-v5",
        host_first_network_device_ip_address="160.48.199.77",
        host_second_network_device_ip_address="192.168.1.99",
    ):
        """Create a QEMU instance with the specified parameters.

        :param str path_to_image: The path to the Qemu image file.
        :param str path_to_bootloader: The path to the Qemu bootloader file.
        :param str ram: The amount of RAM to allocate to the QEMU instance.
        :param str cores: The number of CPU cores to allocate to the QEMU instance.
        :param str cpu: The CPU model to emulate.
         Default is Cascadelake-Server-v5 used to emulate modern Intel CPU features.
         For older Ubuntu versions change that to host in case of errors.
        :param str host_first_network_device_ip_address: The IP address of the first network device on the host.
        :param str host_second_network_device_ip_address: The IP address of the second network device on the host.
        """
        self.__qemu_path = "/usr/bin/qemu-system-x86_64"

        self.__first_network_device_name = "unknown"
        self.__second_network_device_name = "unknown"
        self.__first_network_adapter_mac = "52:54:11:22:33:01"
        self.__second_network_adapter_mac = "52:54:11:22:33:02"
        self.__first_network_device_ip_address = host_first_network_device_ip_address
        self.__second_network_device_ip_address = host_second_network_device_ip_address

        self.__path_to_image = path_to_image
        self.__path_to_bootloader = path_to_bootloader
        self.__ram = ram
        self.__cores = cores
        self.__cpu = cpu

        self.__check_qemu_is_installed()
        self.__find_available_kvm_support()
        self.__check_kvm_readable_when_necessary()
        self.__find_tap_devices()

        self._subprocess = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self, subprocess_params=None):
        logger.debug(self.__build_qemu_command())
        subprocess_args = {"args": shlex.split(self.__build_qemu_command())}
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

    def __find_tap_devices(self):
        for interface in netifaces.interfaces():
            try:
                interface_address = netifaces.ifaddresses(interface)[netifaces.AF_INET][0]["addr"]
                if interface_address == self.__first_network_device_ip_address:
                    self.__first_network_device_name = "tap0"
                if interface_address == self.__second_network_device_ip_address:
                    self.__second_network_device_name = interface
            except KeyError:
                pass

        if "unknown" in (self.__first_network_device_name, self.__second_network_device_name):
            logger.fatal("Could not find correct tap devices. Please setup network for Qemu first!")
            sys.exit(-1)

    def __build_qemu_command(self):
        return (
            f"{self.__qemu_path}"
            " --enable-kvm"  # Use hardware virtualization for better performance
            f" -smp {self.__cores},maxcpus={self.__cores},cores={self.__cores}"
            f" -cpu {self.__cpu}"  # Specify CPU to emulate
            f" -m {self.__ram}"  # Specify RAM size
            f" -kernel {self.__path_to_image}"  # Specify kernel image
            " -nographic"  # Disable graphical display (console-only)
            " -serial mon:stdio"  # Redirect serial output to console
            " -object rng-random,filename=/dev/urandom,id=rng0"  # Provide hardware random number generation
            f" {self.__first_network_adapter()}"
            f" {self.__second_network_adapter()}"
            " -device virtio-rng-pci,rng=rng0"  # Provide hardware random number generation
        )

    def __first_network_adapter(self):
        return (
            f" -netdev tap,id=t1,ifname={self.__first_network_device_name},script=no,downscript=no"
            f" -device virtio-net-pci,netdev=t1,id=nic1,mac={self.__first_network_adapter_mac},guest_csum=off"
        )

    def __second_network_adapter(self):
        return (
            f" -netdev tap,id=t2,ifname={self.__second_network_device_name},script=no,downscript=no"
            f" -device virtio-net-pci,netdev=t2,id=nic2,mac={self.__second_network_adapter_mac},guest_csum=off"
        )
