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
import socket
import pytest

from itf.core.base.constants import TEST_CONFIG_KEY, TARGET_CONFIG_KEY
from itf.core.base.target.config import load_configuration, target_ecu_argparse
from itf.core.base.os.operating_system import OperatingSystem
from itf.core.base.target.qemu_target import qemu_target
from itf.core.base.target.qvp_target import qvp_target
from itf.core.base.target.hw_target import hw_target
from itf.core.base.utils.exec_utils import pre_tests_phase, post_tests_phase
from itf.core.utils import padder
from itf.core.utils.bunch import Bunch


logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--target_config",
        action="store",
        default="config/target_config.json",
        help="Path to json file with target configurations.",
    )
    # Internally provided in py_itf_test macro
    parser.addoption(
        "--dlt_receive_path",
        action="store",
        help="Path to dlt-receive binary",
    )
    parser.addoption(
        "--ecu",
        action="store",
        required=True,
        nargs="?",
        help="Target ECU for testing",
    )
    parser.addoption(
        "--os",
        action="store",
        default=OperatingSystem.LINUX,
        type=OperatingSystem.argparse,
        choices=OperatingSystem,
        nargs="?",
        help="Operating System to run",
    )
    parser.addoption("--qemu", action="store_true", help="Run tests with QEMU image")
    parser.addoption("--qemu_image", action="store", help="Path to a QEMU image")

    parser.addoption("--qvp", action="store_true", help="Run tests with QVP")
    parser.addoption("--hw", action="store_true", help="Run tests against connected HW")


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_sessionstart(session):
    logger.info("Starting session in base_plugin.py ...")
    print(padder("live log sessionstart"))
    session.stash[TEST_CONFIG_KEY] = __make_test_config(session.config)
    session.stash[TARGET_CONFIG_KEY] = __make_target_config(session.stash[TEST_CONFIG_KEY])
    session.ecu_name = session.stash[TEST_CONFIG_KEY].ecu.sut.ecu_name.lower()
    yield


@pytest.fixture(scope="session")
def test_config_fixture(request):
    return request.session.stash[TEST_CONFIG_KEY]


@pytest.fixture(scope="session")
def target_config_fixture(request):
    target_config = request.session.stash[TARGET_CONFIG_KEY]
    yield target_config


@pytest.fixture(scope="session")
def target_fixture(target_config_fixture, test_config_fixture, request):
    logger.info("Starting target_fixture in base_plugin.py ...")
    logger.info(f"Starting tests on host: {socket.gethostname()}")

    if test_config_fixture.qemu:
        with qemu_target(target_config_fixture, test_config_fixture) as qemu:
            try:
                pre_tests_phase(qemu, target_config_fixture.ip_address, test_config_fixture, request)
                yield qemu
            finally:
                post_tests_phase(qemu, test_config_fixture)

    elif test_config_fixture.qvp:
        with qvp_target(target_config_fixture, test_config_fixture) as qvp:
            try:
                pre_tests_phase(qvp, target_config_fixture.ip_address, test_config_fixture, request)
                yield qvp
            finally:
                post_tests_phase(qvp, test_config_fixture)

    elif test_config_fixture.hw:
        with hw_target(target_config_fixture, test_config_fixture) as hardware:
            try:
                pre_tests_phase(hardware, target_config_fixture.ip_address, test_config_fixture, request)
                yield hardware
            finally:
                post_tests_phase(hardware, test_config_fixture)
    else:
        raise RuntimeError("QEMU, QVP or HW not specified to use")


def __make_test_config(config):
    load_configuration(config.getoption("target_config"))
    return Bunch(
        ecu=target_ecu_argparse(config.getoption("ecu")),
        os=config.getoption("os"),
        qemu=config.getoption("qemu"),
        qemu_image=config.getoption("qemu_image"),
        qvp=config.getoption("qvp"),
        hw=config.getoption("hw"),
        dlt_receive_path=config.getoption("dlt_receive_path"),
    )


def __make_target_config(test_config):
    target_config = test_config.ecu.sut
    if test_config.qemu_image:
        target_config.qemu_image_path = test_config.qemu_image
    return target_config
