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
from itf.plugins.base.target.config.base_processor import BaseProcessor


class PerformanceProcessor(BaseProcessor):
    # pylint: disable=dangerous-default-value, too-many-arguments
    def __init__(
        self,
        name: str,
        ip_address: str = None,
        ssh_port: int = 22,
        ext_ip_address: str = None,
        diagnostic_ip_address: str = None,
        diagnostic_address: int = 0,
        serial_device: str = None,
        network_interfaces: list = [],
        ecu_name: str = None,
        data_router_config: dict = None,
        qemu_num_cores: int = 2,
        qemu_ram_size: str = "1G",
        params: dict = None,
    ):
        """Initialize the PerformanceProcessor class.

        :param str name: The name of the processor.
        :param str ip_address: The IP address of the processor.
        :param int ssh_port: The SSH port for the processor.
        :param str ext_ip_address: The external IP address of the processor.
        :param str diagnostic_ip_address: The internal IP address for diagnostics.
        :param int diagnostic_address: The diagnostic address of the processor.
        :param str serial_device: The serial device for the processor.
        :param list network_interfaces: The network interfaces for the processor.
        :param str ecu_name: The ECU name for the processor.
        :param dict data_router_configs: Configuration for the data router
         with keys "vlan_address" and "multicast_addresses".
        :param int qemu_num_cores: The number of CPU cores for QEMU.
        :param str qemu_ram_size: The amount of RAM for QEMU.
        :param dict params: Additional parameters for the processor.
        """
        super().__init__(
            name=name,
            ip_address=ip_address,
            ssh_port=ssh_port,
            diagnostic_ip_address=diagnostic_ip_address,
            diagnostic_address=diagnostic_address,
            serial_device=serial_device,
            params=params,
        )
        self.__ext_ip_address = ext_ip_address
        self.__network_interfaces = network_interfaces
        self.__ecu_name = ecu_name
        self.__data_router_config = data_router_config
        self.__qemu_num_cores = qemu_num_cores
        self.__qemu_ram_size = qemu_ram_size
        self.__qemu_image_path = None

    @property
    def ext_ip_address(self):
        return self.__ext_ip_address

    @property
    def ecu_name(self):
        return self.__ecu_name

    @property
    def network_interfaces(self):
        return self.__network_interfaces

    @property
    def data_router_config(self):
        return self.__data_router_config

    @property
    def qemu_num_cores(self):
        return self.__qemu_num_cores

    @property
    def qemu_ram_size(self):
        return self.__qemu_ram_size

    @property
    def qemu_image_path(self):
        return self.__qemu_image_path

    @qemu_image_path.setter
    def qemu_image_path(self, value):
        self.__qemu_image_path = value

    def update(self, processor):
        """Update the current processor with another processor's parameters.

        :param PerformanceProcessor processor: The PerformanceProcessor instance to update from.
        """
        super().update(processor)
        self.__ext_ip_address = processor.ext_ip_address
        self.__network_interfaces = processor.network_interfaces
        self.__ecu_name = processor.ecu_name
        self.__data_router_config = processor.data_router_config
        self.__qemu_num_cores = processor.num_cores
        self.__qemu_ram_size = processor.ram_size
        self.__qemu_image_path = processor.qemu_image_path

    def __eq__(self, other):
        if isinstance(other, PerformanceProcessor):
            return super().__eq__(other)
        return False

    def __ne__(self, other):
        if isinstance(other, PerformanceProcessor):
            return super().__ne__(other)
        return True

    def __hash__(self):  # pylint: disable=useless-super-delegation
        return super().__hash__()
