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
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--keep-target",
        action="store_true",
        required=False,
        help="Keep the target running between the tests",
    )


def determine_target_scope(fixture_name, config):
    """Determines wether the target should be kept between tests or not

    Plugins should use this function in their target_init (and related) scope definitions.
    """
    if config.getoption("--keep-target", None):
        return "session"
    return "function"


@pytest.fixture(scope=determine_target_scope)
def target(target_init):
    """Use automatic fixture resolution

    Plugins need to define a pytest fixture 'target_init'
    """
    yield target_init
