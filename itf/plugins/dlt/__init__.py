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
import pytest

from itf.core.utils.bunch import Bunch
from itf.plugins.core import determine_target_scope
from itf.plugins.dlt.dlt_receive import DltReceive, Protocol


def pytest_addoption(parser):
    parser.addoption(
        "--dlt-config",
        action="store",
        required=False,
        help="Path to json file with dlt configurations.",
    )
    parser.addoption(
        "--dlt-receive-path",
        action="store",
        required=True,
        help="Path to dlt-receive binary.",
    )


@pytest.fixture(scope="session")
def dlt_config(request):
    b = Bunch(
        host_ip="127.0.0.1",
        target_ip="127.0.0.1",
        multicast_ips=[],
    )

    dlt_config_path = request.config.getoption("dlt_config")
    if dlt_config_path:
        with open(dlt_config_path) as f:
            json_config = json.load(f)
            if "host_ip" in json_config:
                b.host_ip = json_config["host_ip"]
            if "target_ip" in json_config:
                b.target_ip = json_config["target_ip"]
            if "multicast_ips" in json_config:
                b.multicast_ips = json_config["multicast_ips"]

    b.dlt_receive_path = request.config.getoption("dlt_receive_path")

    return b


@pytest.fixture(scope="session")
def dlt(dlt_config):
    with DltReceive(
        protocol=Protocol.UDP,
        host_ip=dlt_config.host_ip,
        multicast_ips=dlt_config.multicast_ips,
        binary_path=dlt_config.dlt_receive_path,
    ):
        yield
