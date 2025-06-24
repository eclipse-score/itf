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
import pytest

from itf.plugins.base.constants import TEST_CONFIG_KEY, TARGET_CONFIG_KEY
from itf.plugins.base.target.config import load_configuration, target_ecu_argparse
from itf.plugins.base.os.operating_system import OperatingSystem
from itf.plugins.utils import padder
from itf.plugins.xtf_common.bunch import Bunch


logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--target_config",
        action="store",
        default="",
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


def __make_test_config(config):
    load_configuration(config.getoption("target_config"))
    return Bunch(
        ecu=target_ecu_argparse(config.getoption("ecu")),
        os=config.getoption("os"),
        qemu=config.getoption("qemu"),
        qvp=config.getoption("qvp"),
        hw=config.getoption("hw"),
    )


def __make_target_config(test_config):
    target_config = test_config.ecu.sut
    return target_config
