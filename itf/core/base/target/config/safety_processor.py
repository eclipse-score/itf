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
from itf.core.base.target.config.base_processor import BaseProcessor


class SafetyProcessor(BaseProcessor):
    def __init__(
        self,
        name: str,
        ip_address: str = None,
        diagnostic_ip_address: str = None,
        diagnostic_address: int = 0,
        serial_device: str = None,
        use_doip: bool = False,
        params: dict = None,
    ):
        """Initialize the SafetyProcessor class.

        :param str name: The name of the processor.
        :param str ip_address: The IP address of the processor.
        :param str diagnostic_ip_address: The internal IP address for diagnostics.
        :param int diagnostic_address: The diagnostic address of the processor.
        :param str serial_device: The serial device for the processor.
        :param bool use_doip: Flag to indicate if DoIP is used.
        :param dict params: Additional parameters for the processor.
        """
        super().__init__(
            name=name,
            ip_address=ip_address,
            diagnostic_ip_address=diagnostic_ip_address,
            diagnostic_address=diagnostic_address,
            serial_device=serial_device,
            use_doip=use_doip,
            params=params,
        )

    def __eq__(self, other):
        if isinstance(other, SafetyProcessor):
            return super().__eq__(other)
        return False

    def __ne__(self, other):
        if isinstance(other, SafetyProcessor):
            return super().__ne__(other)
        return True

    def __hash__(self):  # pylint: disable=useless-super-delegation
        return super().__hash__()
