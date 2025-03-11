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

    # pylint: disable=dangerous-default-value
    def __init__(
        self,
        name: str,
        ip_address: str = None,
        ext_ip_address: str = None,
        diagnostic_ip_address: str = None,
        diagnostic_address: int = 0,
        serial_device: str = None,
        network_interfaces: list = [],
        ecu_name: str = None,
        params: dict = None,
    ):
        """Initialize the PerformanceProcessor class.

        :param str name: The name of the processor.
        :param str ip_address: The IP address of the processor.
        :param str ext_ip_address: The external IP address of the processor.
        :param str diagnostic_ip_address: The internal IP address for diagnostics.
        :param int diagnostic_address: The diagnostic address of the processor.
        :param str serial_device: The serial device for the processor.
        :param list network_interfaces: The network interfaces for the processor.
        :param str ecu_name: The ECU name for the processor.
        :param dict params: Additional parameters for the processor.
        """
        super().__init__(
            name=name,
            ip_address=ip_address,
            diagnostic_ip_address=diagnostic_ip_address,
            diagnostic_address=diagnostic_address,
            serial_device=serial_device,
            params=params,
        )
        self.__ext_ip_address = ext_ip_address
        self.__network_interfaces = network_interfaces
        self.__ecu_name = ecu_name

    @property
    def ext_ip_address(self):
        return self.__ext_ip_address

    @property
    def ecu_name(self):
        return self.__ecu_name

    @property
    def network_interfaces(self):
        return self.__network_interfaces

    def update(self, processor):
        """Update the current processor with another processor's parameters.

        :param PerformanceProcessor processor: The PerformanceProcessor instance to update from.
        """
        super().update(processor)
        self.__ext_ip_address = processor.ext_ip_address
        self.__network_interfaces = processor.network_interfaces
        self.__ecu_name = processor.ecu_name

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
