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
"""The original dlt plugin: its options and the `dlt_config`, `dlt` and `dlt_on_target` fixtures, over the target
file's `logs` and `dlt_on_target` roles."""

import json
from pathlib import Path

import pytest

from ..utils import Bunch
from .core import itf_session, option


def pytest_addoption(parser):
    group = parser.getgroup("itf dlt")
    group.addoption("--dlt-config", help="Path to json file with dlt configurations.")
    group.addoption("--dlt-receive-path", help="Path to dlt-receive binary (the dlt pack ships one).")
    group.addoption(
        "--dlt-receive-on-target-path", help="Path to dlt-receive binary cross-compiled for the target platform."
    )


def settings(config) -> dict:
    path = option(config, "dlt_config")
    found = json.loads(Path(path).read_text(encoding="utf-8")) if path else {}
    return {
        "host_ip": found.get("host_ip", "127.0.0.1"),
        "target_ip": found.get("target_ip", "127.0.0.1"),
        "multicast_ips": found.get("multicast_ips", []),
    }


@pytest.fixture(scope="session")
def dlt_config(request):
    return Bunch(**settings(request.config), dlt_receive_path=option(request.config, "dlt_receive_path"))


@pytest.fixture(scope="session")
def dlt(request):
    """DLT recorded for the session by the target file's `logs` role (the qemu target files start it)."""
    session = itf_session(request.config)
    if session is not None and session.target.has("logs"):
        session.reach("logs.active")
    yield


@pytest.fixture()
def dlt_on_target(request):
    """Start dlt-receive on the target: `with dlt_on_target(Protocol.UDP, ...) as receiver:`, through the target
    file's `dlt_on_target` role; receivers still running stop when the test ends."""
    session = itf_session(request.config)
    if session is None or not session.target.has("dlt_on_target"):
        pytest.fail("dlt_on_target needs a dlt_on_target role (dlt.on_target) in the target file", pytrace=False)
    receivers = session.target.dlt_on_target
    yield receivers.start
    receivers.close()
