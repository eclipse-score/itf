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

from score.itf.plugins.qemu.base.target.processors.target_processor import TargetProcessor
from score.itf.plugins.qemu.base.os.operating_system import OperatingSystem
from score.itf.plugins.qemu.base.target.config.ecu import Ecu

logger = logging.getLogger(__name__)


class Target:
    """Represents a set of Processors"""

    def __init__(
        self,
        target_ecu: Ecu,
        target_sut_os: OperatingSystem = OperatingSystem.LINUX,
        diagnostic_ip: str = None,
    ):
        """Initializes the Target with the given parameters.

        :param Ecu target_ecu: The ECU type for the target.
        :param OperatingSystem target_sut_os: The operating system of the target SUT. Default is LINUX.
        :param str diagnostic_ip: The IP address for diagnostic communication.
        """
        self.__target_ecu = target_ecu
        self.__target_sut_os = target_sut_os
        self.__sut = None
        # Other processors
        for other_ecu in self.target_ecu.others:
            setattr(self, other_ecu.name.lower(), None)  # Will be set when registering processors
        self.__processors = []
        self.__diagnostic_ip = diagnostic_ip

    def __repr__(self):
        return str(self.__dict__)

    def __str__(self):
        return str(self.__dict__)

    # pylint: disable=unused-argument
    def register_processors(self, process=None, initialize_serial_device=True, initialize_serial_logs=True):
        self.__sut = TargetProcessor(
            self.__target_ecu.sut,
            self.__target_sut_os,
            self.__diagnostic_ip,
        )
        self.__processors.append(self.sut)

        for processor in self.target_ecu.others:
            other_processor = TargetProcessor(processor, OperatingSystem.UNSPECIFIED)
            self.__processors.append(other_processor)
            setattr(self, processor.name.lower(), other_processor)

    @property
    def target_ecu(self):
        return self.__target_ecu

    @property
    def target_sut_os(self):
        return self.__target_sut_os

    @property
    def diagnostic_ip(self):
        return self.__diagnostic_ip

    @property
    def sut(self):
        return self.__sut

    @sut.setter
    def sut(self, value):
        self.__sut = value

    @property
    def processors(self):
        return self.__processors

    @processors.setter
    def processors(self, value):
        self.__processors = value

    def teardown(self):
        for processor in self.__processors:
            processor.teardown()
