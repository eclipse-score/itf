"""Bazel interface for running pytest"""

load("@itf_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_test")

def py_itf_test(name, srcs, args = [], data = [], plugins = [], **kwargs):
    pytest_bootstrap = Label("@dependix_itf//:main.py")
    pytest_ini = Label("@dependix_itf//:pytest.ini")

    plugins = ["-p %s" % plugin for plugin in plugins]

    py_test(
        name = name,
        srcs = [
            pytest_bootstrap,
        ] + srcs,
        main = pytest_bootstrap,
        args = args +
               ["-c $(location %s)" % pytest_ini] +
               [
                   "-p no:cacheprovider",
                   "--show-capture=no",
               ] +
               plugins +
               ["$(location %s)" % x for x in srcs],
        deps = [
            requirement("docker"),
            requirement("pytest"),
            "@dependix_itf//:itf",
        ],
        data = [
            pytest_ini,
        ] + data,
        env = {
            "PYTHONDONOTWRITEBYTECODE": "1",
        },
        **kwargs
    )
