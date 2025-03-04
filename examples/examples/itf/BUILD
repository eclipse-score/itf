load("@score_itf//:defs.bzl", "py_itf_test")

py_itf_test(
    name = "test_docker",
    srcs = [
        "test_docker.py",
    ],
    args = [
        "--docker-image-bootstrap=$(location //examples/docker:image_tarball)",
        "--docker-image=score_itf_examples:latest",
    ],
    data = ["//examples/docker:image_tarball"],
    plugins = [
        "itf.plugins.docker",
    ],
)
