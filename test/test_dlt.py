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
import pytest
import time

from itf.plugins.dlt.dlt_receive import DltReceive, Protocol


def test_dlt_standard_config(target, dlt_config):
    with DltReceive(
        protocol=Protocol.UDP,
        host_ip=dlt_config.host_ip,
        target_ip=dlt_config.target_ip,
        multicast_ips=dlt_config.multicast_ips,
        binary_path=dlt_config.dlt_receive_path,
    ):
        time.sleep(1)


def test_dlt_custom_config(target, dlt_config):
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


def get_container_ip(target):
    target.reload()
    return target.attrs["NetworkSettings"]["Networks"]["bridge"]["IPAddress"]


def get_docker_network_gateway(target):
    target.reload()
    return target.attrs["NetworkSettings"]["Networks"]["bridge"]["Gateway"]


def test_dlt_direct_tcp(target, dlt_config, caplog):
    ipaddress = get_container_ip(target)
    target.exec_run(f"/usr/bin/dlt-daemon -d")

    with DltReceive(
        protocol=Protocol.TCP,
        target_ip=ipaddress,
        print_to_stdout=True,
        logger_name="fixed_dlt_receive",
        binary_path=dlt_config.dlt_receive_path,
    ):
        for i in range(10):
            target.exec_run(f'/bin/sh -c "echo message{i} | /usr/bin/dlt-adaptor-stdin"')

        target.exec_run(f'/bin/sh -c "echo This is a secret message | /usr/bin/dlt-adaptor-stdin"')

        for i in range(10):
            target.exec_run(f'/bin/sh -c "echo message{i} | /usr/bin/dlt-adaptor-stdin"')

    captured_logs = []
    for record in caplog.records:
        if record.name == "fixed_dlt_receive":
            if "This is a secret message" in record.getMessage():
                break
    else:
        pytest.fail("Expected DLT message was not received")


def test_dlt_multicast_udp(target, dlt_config, caplog):
    ipaddress = get_container_ip(target)
    gateway = get_docker_network_gateway(target)
    target.exec_run(f"/usr/bin/dlt-daemon -d")

    with DltReceive(
        protocol=Protocol.UDP,
        host_ip="172.17.0.1",
        multicast_ips=["224.0.0.1"],
        print_to_stdout=True,
        logger_name="fixed_dlt_receive",
        binary_path=dlt_config.dlt_receive_path,
    ):
        for i in range(10):
            target.exec_run(f'/bin/sh -c "echo message{i} | /usr/bin/dlt-adaptor-stdin"')

        target.exec_run(f'/bin/sh -c "echo This is a secret message | /usr/bin/dlt-adaptor-stdin"')

        for i in range(10):
            target.exec_run(f'/bin/sh -c "echo message{i} | /usr/bin/dlt-adaptor-stdin"')

    captured_logs = []
    for record in caplog.records:
        if record.name == "fixed_dlt_receive":
            if "This is a secret message" in record.getMessage():
                break
    else:
        pytest.fail("Expected DLT message was not received")
