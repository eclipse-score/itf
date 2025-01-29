load("//:defs.bzl", "py_itf_test")

py_itf_test(
    name = "test_rules_are_working_correctly",
    srcs = [
        "conftest.py",
        "test_rules_are_working_correctly.py",
    ],
)

py_itf_test(
    name = "test_docker",
    srcs = [
        "test_docker.py",
    ],
    args = [
        "--docker-image=ubuntu:24.04",
    ],
    plugins = [
        "itf.plugins.docker",
    ],
)
