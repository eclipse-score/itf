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


CONSOLE_WIDTH = 80
logger = logging.getLogger(__name__)


def padder(string: str, length: int = CONSOLE_WIDTH) -> str:
    """Pad a string with dashes to fit in a given length.

    :param str string: The string to pad.
    :param int length: The total length of the padded string, defaults to CONSOLE_WIDTH.
    :return: The padded string.
    :rtype: str
    """
    str_len = len(string)
    left = round((length - 2 - str_len) / 2)
    right = length - 2 - str_len - left
    return f"{left * '-'} {string} {right * '-'}"
