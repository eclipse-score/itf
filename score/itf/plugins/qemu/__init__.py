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

from score.itf.plugins.qemu.base.constants import TEST_CONFIG_KEY, TARGET_CONFIG_KEY
from score.itf.plugins.qemu.base.target.config import load_configuration, target_ecu_argparse
from score.itf.plugins.qemu.base.os.operating_system import OperatingSystem
from score.itf.plugins.qemu.base.target.qemu_target import qemu_target
from score.itf.plugins.qemu.base.utils.exec_utils import pre_tests_phase, post_tests_phase
from score.itf.core.utils import padder
from score.itf.core.utils.bunch import Bunch

logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--target_config",
        action="store",
        default="config/target_config.json",
        help="Path to json file with target configurations.",
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
def dlt():
    """Overrideable fixture for enabling dlt collection.
    The DLT plugin should be loaded after the base plugin.
    """
    pass


@pytest.fixture(scope="session")
def target_fixture(target_config_fixture, test_config_fixture, request, dlt):
    logger.info("Starting target_fixture in base_plugin.py ...")
    logger.info(f"Starting tests on host: {socket.gethostname()}")

    with qemu_target(target_config_fixture, test_config_fixture) as qemu:
        try:
            pre_tests_phase(qemu, target_config_fixture.ip_address, test_config_fixture, request)
            yield qemu
        finally:
            post_tests_phase(qemu, test_config_fixture)


def __make_test_config(config):
    load_configuration(config.getoption("target_config"))
    return Bunch(
        ecu=target_ecu_argparse(config.getoption("ecu")),
        os=config.getoption("os"),
        qemu=config.getoption("qemu"),
        qemu_image=config.getoption("qemu_image"),
    )


def __make_target_config(test_config):
    target_config = test_config.ecu.sut
    if test_config.qemu_image:
        target_config.qemu_image_path = test_config.qemu_image
    return target_config
