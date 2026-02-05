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
import time

from itf.plugins.dlt.dlt_receive import DltReceive, Protocol


def test_dlt(dlt_config):
    with DltReceive(
        protocol=Protocol.UDP,
        host_ip=dlt_config.host_ip,
        target_ip=dlt_config.target_ip,
        multicast_ips=dlt_config.multicast_ips,
        binary_path=dlt_config.dlt_receive_path,
    ):
        time.sleep(1)


def test_dlt_custom_config(dlt_config):
    with DltReceive(
        protocol=Protocol.UDP,
        host_ip="127.0.0.1",
        target_ip="127.0.0.1",
        multicast_ips=[
            "239.255.42.99",
            "231.255.42.99",
            "234.255.42.99",
            "237.255.42.99",
        ],
        binary_path=dlt_config.dlt_receive_path,
    ):
        time.sleep(1)
