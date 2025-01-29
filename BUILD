load("@rules_python//python:defs.bzl", "py_library")
load("@rules_python//python:pip.bzl", "compile_pip_requirements")

compile_pip_requirements(
    name = "requirements",
    src = "requirements.in",
    requirements_txt = "requirements_lock.txt",
)

exports_files([
    "main.py",
    "pytest.ini",
])

py_library(
    name = "itf",
    srcs = [
        "itf/plugins/docker.py",
    ],
    imports = ["."],
    visibility = ["//visibility:public"],
)

test_suite(
    name = "format.check",
    tests = ["//tools/format:format.check"],
)

alias(
    name = "format.fix",
    actual = "//tools/format:format.fix",
)

exports_files([
    ".ruff.toml",
])
