load("//bazel:py_itf_plugin.bzl", "py_itf_plugin")

docker = py_itf_plugin(
    py_library = "@score_itf//itf/plugins:docker",
    enabled_plugins = [
        "itf.plugins.docker",
    ],
    args = [
    ],
    data = [
    ],
    data_as_exec = [
    ],
    tags = [
    ],
)

base = py_itf_plugin(
    py_library = "@score_itf//itf/core/base",
    enabled_plugins = [
        "itf.core.base.base_plugin",
    ],
    args = [
        "--dlt_receive_path=$(location @score_itf//itf/core/dlt:dlt-receive_as_host)",
    ],
    data = [
    ],
    data_as_exec = [
        "@score_itf//itf/core/dlt:dlt-receive_as_host",
        "@score_itf//itf/core/dlt:libdlt_as_host.so",
    ],
    tags = [
        "local",
        "manual",
    ],
)
