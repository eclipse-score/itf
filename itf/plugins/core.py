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
