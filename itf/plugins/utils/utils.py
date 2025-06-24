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
CONSOLE_WIDTH = 80

def padder(string, length=CONSOLE_WIDTH):
    str_len = len(string)
    left = round((length - 2 - str_len) / 2)
    right = length - 2 - str_len - left
    return f'{left*"-"} {string} {right*"-"}'
