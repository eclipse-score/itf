import logging
import subprocess
import docker as pypi_docker
import pytest


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


@pytest.fixture()
def docker(request):
    docker_image_bootstrap = request.config.getoption("docker_image_bootstrap")
    if docker_image_bootstrap:
        logger.info(
            f"Executing custom image bootstrap command: {docker_image_bootstrap}"
        )
        subprocess.run([docker_image_bootstrap], check=True)

    docker_image = request.config.getoption("docker_image")
    client = pypi_docker.from_env()
    container = client.containers.run(
        docker_image, "sleep infinity", detach=True, auto_remove=True, init=True
    )
    yield container
    container.stop(timeout=1)
