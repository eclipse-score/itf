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
import json
from typing import Optional


class BaseProcessor:
    def __init__(
        self,
        name: str,
        ip_address: Optional[str] = None,
        ssh_port: int = 22,
        diagnostic_ip_address: Optional[str] = None,
        diagnostic_address: Optional[int] = None,
        serial_device: Optional[str] = None,
        use_doip: bool = False,
        params: Optional[dict] = None,
    ):
        """Initialize the BaseProcessor class.

        :param str name: The name of the processor.
        :param str ip_address: The IP address of the processor.
        :param int ssh_port: The SSH port for the processor.
        :param str diagnostic_ip_address: The internal IP address for diagnostics.
        :param int diagnostic_address: The diagnostic address of the processor.
        :param str serial_device: The serial device for the processor.
        :param bool use_doip: Flag to indicate if DoIP is used
        :param dict params: Additional parameters for the processor.
        """
        self.__name = name
        self.__ip_address = ip_address
        self.__ssh_port = ssh_port
        self.__diagnostic_ip_address = diagnostic_ip_address
        self.__diagnostic_address = diagnostic_address
        self.__serial_device = serial_device
        self.__use_doip = use_doip
        self.__params = params
        if params:
            self.__dict__.update(**params)

    @property
    def name(self) -> str:
        return self.__name

    @property
    def ip_address(self):
        return self.__ip_address

    @property
    def ssh_port(self):
        return self.__ssh_port

    @ip_address.setter
    def ip_address(self, value):
        self.__ip_address = value

    @property
    def diagnostic_ip_address(self):
        return self.__diagnostic_ip_address

    @property
    def diagnostic_address(self):
        return self.__diagnostic_address

    @property
    def serial_device(self):
        return self.__serial_device

    @property
    def use_doip(self):
        return self.__use_doip

    @use_doip.setter
    def use_doip(self, value):
        self.__use_doip = value

    @property
    def params(self):
        return self.__params

    def get_param(self, param_name: str):
        """Get a specific parameter by name.

        :param str param_name: The name of the parameter.
        :return: The value of the parameter.
        """
        if self.__dict__ is not None:
            return self.__dict__[param_name]
        return None

    def set_param(self, param_name: str, param_value):
        """Add or update a parameter in the processor's parameters.

        :param str param_name: The name of the parameter.
        :param param_value: The value of the parameter.
        """
        self.__params[param_name] = param_value
        if self.__dict__ is not None:
            self.__dict__[param_name] = param_value

    def get(self, *args, **kwargs):
        return self.__dict__.get(args, kwargs)

    def update(self, processor):
        """Update the current processor with another processor's parameters.

        :param BaseProcessor processor: The BaseProcessor instance to update from.
        """
        self.__ip_address = processor.ip_address
        self.__ssh_port = processor.ssh_port
        self.__diagnostic_ip_address = processor.diagnostic_ip_address
        self.__diagnostic_address = processor.diagnostic_address
        self.__serial_device = processor.serial_device
        self.__use_doip = processor.use_doip
        if processor.params:
            self.__dict__.update(**processor.params)
            if self.__params:
                self.__params.update(processor.params)
            else:
                self.__params = processor.params

    def __str__(self):
        return self.__name.upper()

    def __repr__(self):
        return f"{self.__name.upper()} ({json.dumps(self.__dict__, indent=4)})"

    def __eq__(self, other):
        if isinstance(other, BaseProcessor):
            return self.__name == other.name
        return False

    def __ne__(self, other):
        if isinstance(other, BaseProcessor):
            return self.name != other.name
        return True

    def __hash__(self):
        return hash(self.__name)
