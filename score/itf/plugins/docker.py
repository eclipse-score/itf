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
import subprocess
import docker as pypi_docker
import pytest

from score.itf.plugins.core import determine_target_scope
from score.itf.plugins.core import Target

from score.itf.core.com.ssh import Ssh


logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--docker-image",
        action="store",
        required=True,
        help="Docker image to run tests against.",
    )
    parser.addoption(
        "--docker-image-bootstrap",
        action="store",
        required=False,
        help="Docker image bootstrap command, that will be executed before referencing the container.",
    )


DOCKER_CAPABILITIES = ["exec"]


class DockerTarget(Target):
    def __init__(self, container, capabilities=DOCKER_CAPABILITIES):
        super().__init__(capabilities=capabilities)
        self.container = container

    def __getattr__(self, name):
        return getattr(self.container, name)

    def get_ip(self):
        self.container.reload()
        return self.container.attrs["NetworkSettings"]["Networks"]["bridge"]["IPAddress"]

    def get_gateway(self):
        self.container.reload()
        return self.container.attrs["NetworkSettings"]["Networks"]["bridge"]["Gateway"]

    def ssh(self, username="score", password="score", port=2222):
        return Ssh(target_ip=self.get_ip(), port=port, username=username, password=password)


@pytest.fixture(scope=determine_target_scope)
def docker_configuration():
    """
    Fixture that provides a customization point for Docker configuration in tests.

    This fixture allows tests to override and customize Docker settings by providing
    a dictionary of configuration parameters. Tests can use this fixture to inject
    custom Docker configuration values as needed for their specific test scenarios.

    Returns:
        dict: An empty dictionary that can be populated with custom Docker configuration
            parameters by tests or through pytest fixtures/parametrization.

    Scope:
        The fixture scope is determined dynamically based on the target scope.
    """
    return {}


@pytest.fixture(scope=determine_target_scope)
def _docker_configuration(docker_configuration):
    configuration = {
        "environment": {},
        "command": "sleep infinity",
        "init": True,
    }
    merged_configuration = {**configuration, **docker_configuration}

    return merged_configuration


@pytest.fixture(scope=determine_target_scope)
def target_init(request, _docker_configuration):
    print(_docker_configuration)

    docker_image_bootstrap = request.config.getoption("docker_image_bootstrap")
    if docker_image_bootstrap:
        logger.info(f"Executing custom image bootstrap command: {docker_image_bootstrap}")
        subprocess.run([docker_image_bootstrap], check=True)

    docker_image = request.config.getoption("docker_image")
    client = pypi_docker.from_env()
    container = client.containers.run(
        docker_image,
        _docker_configuration["command"],
        detach=True,
        auto_remove=True,
        init=_docker_configuration["init"],
        environment=_docker_configuration["environment"],
    )
    yield DockerTarget(container)
    container.stop(timeout=1)
