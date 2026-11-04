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
"""The original docker plugin: its options, the `docker_configuration` fixture and a `target_init` serving a
`DockerTarget`.

`--docker-image` selects the Docker target file shipped in `targets/` (`docker_dlt` with the dlt plugin). Add
`--docker-ssh` for an image that runs an SSH server. Unless `--itf-target` names the project's own target file,
the shipped compatibility target is used with the same fixtures.
"""

import os

import pytest

from ..legacy import DockerTarget
from .core import determine_target_scope, itf_session, option
from .targets import select

# docker_configuration keys the platform role takes, as the original plugin passed them to the container.
CONFIGURABLE = ("command", "init", "environment", "volumes", "shm_size", "privileged")


def pytest_addoption(parser):
    group = parser.getgroup("itf docker")
    group.addoption("--docker-image", help="Docker image to run tests against.")
    group.addoption("--docker-image-bootstrap", help="Command run before the image is referenced (e.g. oci_load).")
    group.addoption(
        "--docker-ssh",
        action="store_true",
        help="Declare SSH/SFTP capabilities for a Docker image that runs an SSH server.",
    )
    group.addoption(
        "--extract-coverage",
        action="store_true",
        default=False,
        help="Extract coverage files (.gcda) from the container before teardown.",
    )
    group.addoption("--coverage-output-dir", default=None, help="Where extracted coverage files go.")


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    image = option(config, "docker_image")
    if image:
        select(
            config,
            "docker",
            {
                "LEGACY_DOCKER_IMAGE": image,
                "LEGACY_DOCKER_BOOTSTRAP": option(config, "docker_image_bootstrap"),
                "LEGACY_EXTRACT_COVERAGE": "true" if option(config, "extract_coverage") else "false",
                "LEGACY_COVERAGE_DIR": option(config, "coverage_output_dir"),
                # the original plugin's fixed login for SSH images, unless the environment gives another
                "LEGACY_SSH_USER": os.environ.get("LEGACY_SSH_USER", "score"),
                "LEGACY_SSH_PASSWORD": os.environ.get("LEGACY_SSH_PASSWORD", "score"),
            },
        )


@pytest.fixture(scope=determine_target_scope)
def docker_configuration():
    """Override to customize the container: command, init, environment, volumes, shm_size, privileged."""
    return {}


_applied: dict = {}  # the docker_configuration the running container was started with


@pytest.fixture(scope=determine_target_scope)
def target_init(request, docker_configuration):
    """A fresh container per test (once with --keep-target) with `docker_configuration` applied."""
    session = itf_session(request.config)
    if session is None:
        raise pytest.UsageError("the docker plugin needs --docker-image (or --itf-target)")
    unknown = sorted(set(docker_configuration) - set(CONFIGURABLE))
    if unknown:
        raise pytest.UsageError(
            f"docker_configuration keys {unknown} are not supported; supported: {', '.join(CONFIGURABLE)}"
        )
    platform = session.target.platform
    keep = option(request.config, "keep_target")
    if platform.running() and (not keep or _applied.get("configuration") != docker_configuration):
        session.discard("platform")  # a fresh platform, which the settings below apply to
        platform = session.target.platform
    if not platform.running():
        for key, value in docker_configuration.items():
            setattr(platform, key, value)
        session.reach("platform.up")
        _applied["configuration"] = dict(docker_configuration)
    yield DockerTarget(session.target)
