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
import logging
from contextlib import contextmanager

import pytest

from score.itf.core.utils.bunch import Bunch
from score.itf.plugins.dlt.dlt_receive import DltReceive, Protocol, protocol_arguments


logger = logging.getLogger(__name__)


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
    parser.addoption(
        "--dlt-receive-on-target-path",
        action="store",
        required=False,
        help="Path to dlt-receive binary cross-compiled for the target platform.",
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


_DLT_RECEIVE_REMOTE_PATH = "/tmp/dlt-receive"
_DLT_OUTPUT_DIR = "/tmp"


class DltReceiver:
    """Thin wrapper around an :class:`AsyncProcess` that also tracks the DLT output file."""

    def __init__(self, proc, dlt_file=None):
        self._proc = proc
        self.dlt_file = dlt_file

    def __getattr__(self, name):
        return getattr(self._proc, name)


@pytest.fixture()
def dlt_on_target(request, target, dlt_config):
    """Upload ``dlt-receive`` to the target and yield a factory for starting it.

    The factory returns a :class:`DltReceiver` handle that delegates to the
    underlying :class:`~score.itf.core.process.async_process.AsyncProcess`.
    All receivers started via the factory are stopped automatically when the
    fixture tears down.

    Example usage::

        def test_example(target, dlt_on_target):
            with target.wrap_exec("/usr/bin/dlt-daemon"):
                with dlt_on_target(Protocol.UDP, multicast_ips=["224.0.0.1"]) as receiver:
                    # ... send messages ...
                    pass
                assert "expected" in receiver.get_output()
                target.download(receiver.dlt_file, "local_trace.dlt")
    """
    # Note: Currently dlt_on_target is only used on docker Linux,
    # so we default to the host-built binary
    on_target_path = request.config.getoption("dlt_receive_on_target_path", default=None)
    local_binary = on_target_path or dlt_config.dlt_receive_path

    target.upload(local_binary, _DLT_RECEIVE_REMOTE_PATH)
    target.execute(f"chmod +x {_DLT_RECEIVE_REMOTE_PATH}")

    receivers = []
    _counter = 0

    @contextmanager
    def start(
        protocol,
        host_ip="127.0.0.1",
        target_ip="127.0.0.1",
        multicast_ips=None,
        print_to_stdout=True,
        output_file=None,
    ):
        nonlocal _counter
        _counter += 1
        dlt_file = output_file or f"{_DLT_OUTPUT_DIR}/dlt-receive-{_counter}.dlt"

        args = protocol_arguments(protocol, host_ip, target_ip, multicast_ips or [])
        args += ["-o", dlt_file]
        if print_to_stdout:
            args += ["-a", "--stdout-flush"]
        proc = target.execute_async(_DLT_RECEIVE_REMOTE_PATH, args=args)
        receiver = DltReceiver(proc, dlt_file=dlt_file)
        receivers.append(proc)
        try:
            yield receiver
        finally:
            if proc.is_running():
                proc.stop()

    yield start

    for proc in receivers:
        try:
            if proc.is_running():
                proc.stop()
        except Exception:
            logger.warning("Failed to stop on-target dlt-receive", exc_info=True)
