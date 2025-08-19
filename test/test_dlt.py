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
from itf.plugins.dlt.dlt_receive import DltReceive, Protocol
import time


def test_dlt():
    with DltReceive(
        target_ip="127.0.0.1",
        protocol=Protocol.UDP,
        binary_path="./itf/plugins/dlt/dlt-receive",
        data_router_config={
            "vlan_address": "127.0.0.1",
            "multicast_addresses": [
                "239.255.42.99",
                "231.255.42.99",
                "234.255.42.99",
                "237.255.42.99",
            ],
        },
    ):
        time.sleep(5)
        pass
