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
"""The original core plugin: `--keep-target`, the `target_init` → `target` fixture chain, `requires_capabilities`,
and the one notice per run that the compatibility layer is in use.

`py_itf_test` loads it for every test that names no `itf_target`, as the original rule loaded
`score.itf.plugins.core`. With a target file (from the docker or qemu options, or `--itf-target`), `target` is a
`LegacyTarget` over it; without one, an `UnsupportedTarget`, as before. A project's own plugin that provides
`target_init` keeps working.
"""

import functools

import pytest

from ..notice import ItfCompatibilityWarning
from ..legacy import LegacyTarget
from ..target import UnsupportedTarget

# The original plugins whose use makes a run a compatibility run (the core plugin alone does not).
ORIGINAL_PLUGINS = ("docker", "qemu", "dlt", "core_dump")


def pytest_addoption(parser):
    parser.addoption(
        "--keep-target",
        action="store_true",
        required=False,
        help="Keep the target running between the tests",
    )


def option(config, name):
    """An option of another original plugin; None when that plugin is not loaded."""
    try:
        return config.getoption(name)
    except ValueError:
        return None


def itf_session(config):
    return getattr(config, "_itf_session", None)


@pytest.hookimpl
def pytest_itf_session_created(config, session, contributors):
    from score.itf.core.frontends.target_source import load_policy

    from .targets import TARGET_FILES

    source = session.target_source
    if source is not None and source.path is not None and source.path.resolve().parent == TARGET_FILES.resolve():
        session._contributors = [*contributors, (load_policy(TARGET_FILES / "policy.py"), "policy")]


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    used = [n for n in ORIGINAL_PLUGINS if config.pluginmanager.hasplugin(f"score.itf.plugins.{n}")]
    if used:
        config.issue_config_time_warning(
            ItfCompatibilityWarning(
                f"this run uses ITF's original {', '.join(used)} plugin(s) through the compatibility layer. "
                "They keep working for the deprecation period; to migrate, `itf compat report` lists what the tests "
                "use and `itf compat target` writes the target file to start from (docs/how-to/migrate.md)."
            ),
            stacklevel=2,
        )


def determine_target_scope(fixture_name, config):
    """Determines wether the target should be kept between tests or not

    Plugins should use this function in their target_init (and related) scope definitions.
    """
    if config.getoption("--keep-target", None):
        return "session"
    return "function"


@pytest.fixture(scope=determine_target_scope)
def target_init(request):
    """The original target over the session's target file, or no capabilities without one."""
    session = itf_session(request.config)
    yield LegacyTarget(session.target) if session is not None else UnsupportedTarget()


@pytest.fixture(scope=determine_target_scope)
def target(target_init):
    """Use automatic fixture resolution

    Plugins need to define a pytest fixture 'target_init'
    """
    yield target_init


def requires_capabilities(*capabilities):
    """Decorator to skip tests if target doesn't have all required capabilities.

    The new API gates with `@itf.requires(role)` instead, before the run.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            target = kwargs.get("target")
            if target is None:
                target = next((arg for arg in args if hasattr(arg, "has_all_capabilities")), None)
            if target and not target.has_all_capabilities(set(capabilities)):
                pytest.skip(f"Target missing required capabilities: {capabilities}")
            return func(*args, **kwargs)

        return wrapper

    return decorator
