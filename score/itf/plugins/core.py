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
import functools

from score.itf.core.target import Target


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
def target_init():
    """Fixture to initialize the target.

    Plugins need to implement this fixture to provide the actual target instance.
    The scope of this fixture is determined by the --keep-target command line option.
    """
    yield Target()


@pytest.fixture(scope=determine_target_scope)
def target(target_init):
    """Use automatic fixture resolution

    Plugins need to define a pytest fixture 'target_init'
    """
    yield target_init


def requires_capabilities(*capabilities):
    """Decorator to skip tests if target doesn't have all required capabilities.

    Args:
        *capabilities: Variable number of capability identifiers required for the test.

    Example:
        @requires_capabilities("exec", "ssh")
        def test_remote_command(target):
            target.exec_run("ls -la")
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            target = kwargs.get("target")
            if target is None:
                for arg in args:
                    if hasattr(arg, "has_all_capabilities"):
                        target = arg
                        break

            if target and not target.has_all_capabilities(set(capabilities)):
                pytest.skip(f"Target missing required capabilities: {capabilities}")

            return func(*args, **kwargs)

        return wrapper

    return decorator
