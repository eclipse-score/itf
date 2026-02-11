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
from typing import List
from score.itf.plugins.qemu.base.target.config.base_processor import BaseProcessor
from score.itf.plugins.qemu.base.target.config.performance_processor import PerformanceProcessor


class Ecu:
    # pylint: disable=dangerous-default-value
    def __init__(
        self,
        name: str,
        sut: PerformanceProcessor,
        others: List[BaseProcessor] = [],
    ):
        """Initialize the Ecu class.

        :param str name: The name of the ECU.
        :param sut: The SUT (Software Under Test) processor.
        :param others: A list of other processors associated with the ECU.
        """
        self.__name = name
        self.__sut = sut
        self.__others = others

    @property
    def name(self):
        return self.__name

    @property
    def sut(self):
        return self.__sut

    @property
    def others(self):
        return self.__others

    def __str__(self):
        return str(self.__name).upper()

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if isinstance(other, Ecu):
            return self.__name == other.name
        return False

    def __ne__(self, other):
        if isinstance(other, Ecu):
            return self.__name != other.name
        return True

    def __hash__(self):
        return hash(self.__name)
