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
        qemu_arch,
        path_to_image,
        score_disk=None,
        ram="1G",
        cores="2",
        cpu="cortex-a57",
        network_adapters=[],
        host_qemu_network=None,
    ):
        """Create a QEMU instance with the specified parameters.

        :param str path_to_image: The path to the Qemu image file.
        :param str ram: The amount of RAM to allocate to the QEMU instance.
        :param str cores: The number of CPU cores to allocate to the QEMU instance.
        :param str cpu: The CPU model to emulate.
         Default is cortex-a57 for aarch64.
        :param host_qemu_network: HostQemuNetwork config with subnet, guest_ip,
         mac_address and port_forwarding rules.
        """
        self.__qemu_arch = qemu_arch
        if self.__qemu_arch == "aarch64":
            self.__qemu_path = "/usr/bin/qemu-system-aarch64"
        else:
            self.__qemu_path = "/usr/bin/qemu-system-x86_64"
        self.__path_to_image = path_to_image
        self.__score_disk = score_disk
        self.__ram = ram
        self.__cores = cores
        self.__cpu = cpu
        self.__network_adapters = network_adapters
        self.__host_qemu_network = host_qemu_network

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
        if self.__qemu_arch == "x86_64":
            return (
                [
                    f"{self.__qemu_path}",
                    "-cpu", "host",
                    "-accel", "kvm",
                    "-smp",
                    f"{self.__cores},maxcpus={self.__cores},cores={self.__cores}",
                    "-m",
                    f"{self.__ram}",  # Specify RAM size
                    "-kernel",
                    f"{self.__path_to_image}",  # Specify kernel image
                ]
                + self.__disk_drive_args()
                + self.__port_forwarding_args()
                + [
                    "-nographic",
                    "-object",
                    "rng-random,filename=/dev/urandom,id=rng0",
                    "-device",
                    "virtio-rng-pci,rng=rng0",
                    "-serial",
                    "mon:stdio",
                ]
                + self.__network_devices_args()
            )
        else:
            return (
                [
                    f"{self.__qemu_path}",
                    "-machine", "virt-4.2",
                    "-cpu",
                    f"{self.__cpu}",
                    "-smp",
                    f"{self.__cores}",
                    "-m",
                    f"{self.__ram}",
                    "-kernel",
                    f"{self.__path_to_image}",
                ]
                + self.__disk_drive_args()
                + self.__port_forwarding_args()
                + [
                    "-nographic",
                    "-object",
                    "rng-random,filename=/dev/urandom,id=rng0",
                    "-device",
                    "virtio-rng-device,rng=rng0",
                    "-serial",
                    "mon:stdio",
                ]
                + self.__network_devices_args()
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

    def __disk_drive_args(self):
        """Build disk drive arguments for virtio-blk-device (aarch64)."""
        if not self.__score_disk:
            return []
        if not os.path.isfile(self.__score_disk):
            logger.info(f"Creating disk image: {self.__score_disk}")
            subprocess.run(
                ["qemu-img", "create", "-f", "qcow2", self.__score_disk, "512M"],
                check=True,
            )
        if self.__qemu_arch == "aarch64":
            return [
                "-drive",
                f"file={self.__score_disk},if=none,id=drv0",
                "-device",
                "virtio-blk-device,drive=drv0",
            ]
        else:
            return [
                "-drive",
                f"file={self.__score_disk},if=none,id=drv0",
                "-device",
                "virtio-blk-pci,drive=drv0",
            ]
            
    def __port_forwarding_args(self):
        """Build port-forwarding arguments.

        For aarch64, all forwarding rules are combined into a single
        ``-netdev user`` entry with a ``-device virtio-net-device``.
        For x86_64, each rule gets its own ``-netdev``/``-device`` pair.
        """
        if self.__host_qemu_network is None:
            return []

        pf_rules = self.__host_qemu_network.port_forwarding
        if not pf_rules:
            return []

        guest_ip = self.__host_qemu_network.ip_address
        subnet = self.__host_qemu_network.subnet
        mac = self.__host_qemu_network.mac_address

        if self.__qemu_arch == "aarch64":
            # Single -netdev user with all hostfwd entries
            hostfwd_parts = ",".join(
                f"hostfwd=tcp::{pf.host_port}-{guest_ip}:{pf.target_port}"
                for pf in pf_rules
            )
            netdev = f"user,id=net0,net={subnet},{hostfwd_parts}"
            return [
                "-netdev", netdev,
                "-device", f"virtio-net-device,mac={mac},netdev=net0",
            ]
        else:
            # Single -netdev user with all hostfwd entries
            hostfwd_parts = ",".join(
                f"hostfwd=tcp::{pf.host_port}-{guest_ip}:{pf.target_port}"
                for pf in pf_rules
            )
            netdev = f"user,id=net0,net={subnet},{hostfwd_parts}"
            return [
                "-netdev", netdev,
                "-device", f"virtio-net-pci,mac={mac},netdev=net0",
            ]

