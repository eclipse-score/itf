# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
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
"""Any target with a recorded console (`console`): UART, an emulator's serial port."""

import score.itf as itf


@itf.requires("console")
def test_the_console_recorded_output_since_it_opened(target):
    assert target.console.lines(), "the console recorded nothing since before boot"
