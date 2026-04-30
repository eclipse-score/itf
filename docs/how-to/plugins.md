# Using Plugins

ITF's functionality is delivered through plugins. Each plugin activates a
target type or a supporting capability (such as DLT message capture).

## Built-in plugins

| Plugin label | Provides | Key CLI arg |
|---|---|---|
| `@score_itf//score/itf/plugins:docker_plugin` | Docker target | `--docker-image` |
| `@score_itf//score/itf/plugins:qemu_plugin` | QEMU target | `--qemu-image`, `--qemu-config` |
| `@score_itf//score/itf/plugins:dlt_plugin` | DLT capture | `--dlt-receive-path`, `--dlt-config` |
| `@score_itf//score/itf/plugins:attribute_plugin` | Requirement traceability | N/A |

> **Plugin loading order:** The core plugin is always loaded first. Additional
> plugins are loaded in the order they appear in `plugins = [...]`. Plugins
> are designed to be independent — do not write tests that rely on one plugin
> having initialised before another.

## Docker plugin

```starlark
load("@score_itf//:defs.bzl", "py_itf_test")

py_itf_test(
    name = "test_docker",
    srcs = ["test_docker.py"],
    args = ["--docker-image=ubuntu:24.04"],
    plugins = ["@score_itf//score/itf/plugins:docker_plugin"],
)
```

Pass `--docker-image` as a Bazel test arg or hard-code it in `args`.

## QEMU plugin

```starlark
py_itf_test(
    name = "test_qemu",
    srcs = ["test_qemu.py"],
    args = [
        "--qemu-image=$(location //path:qemu_image)",
        "--qemu-config=$(location qemu_config.json)",
    ],
    data = [
        "//path:qemu_image",
        "qemu_config.json",
    ],
    plugins = ["@score_itf//score/itf/plugins:qemu_plugin"],
)
```

## DLT plugin

Combine the DLT plugin with a target plugin to enable log capture:

```starlark
py_itf_test(
    name = "test_with_dlt",
    srcs = ["test_with_dlt.py"],
    args = [
        "--docker-image=my-app:latest",
        "--dlt-config=$(location dlt_config.json)",
    ],
    data = ["dlt_config.json"],
    plugins = [
        "@score_itf//score/itf/plugins:docker_plugin",
        "@score_itf//score/itf/plugins:dlt_plugin",
    ],
)
```

DLT configuration file (`dlt_config.json`):

```json
{
    "target_ip": "192.168.122.76",
    "host_ip": "192.168.122.1",
    "multicast_ips": ["239.255.42.99"]
}
```

In the test, use `DltWindow` to capture and query DLT messages:

```python
from score.itf.plugins.dlt.dlt_window import DltWindow
from score.itf.plugins.dlt.dlt_receive import Protocol
import re

def test_dlt_messages(target, dlt_config):
    with DltWindow(
        protocol=Protocol.UDP,
        host_ip="127.0.0.1",
        multicast_ips=["224.0.0.1"],
        binary_path=dlt_config.dlt_receive_path,
    ) as window:
        with target.ssh() as ssh:
            ssh.execute_command("my_application")

        record = window.record()
        results = record.find(query={
            "apid": re.compile(r"APP1"),
            "payload": re.compile(r".*Started successfully.*"),
        })
        assert len(results) > 0
```

## Creating a custom plugin

Implement the `Target` abstract class and a `target_init` fixture:

```python
# my_plugin.py
import pytest
from score.itf.plugins.core import Target, determine_target_scope

MY_CAPABILITIES = ["custom_feature"]

class MyTarget(Target):
    def __init__(self):
        super().__init__(capabilities=MY_CAPABILITIES)

    def execute(self, command):
        pass  # implementation

    def execute_async(self, binary_path, args=None, cwd="/"):
        pass  # implementation

    def upload(self, local_path, remote_path):
        pass  # implementation

    def download(self, remote_path, local_path):
        pass  # implementation

    def restart(self):
        pass  # implementation

@pytest.fixture(scope=determine_target_scope)
def target_init():
    yield MyTarget()
```

Register the plugin with `py_itf_plugin`:

```starlark
load("@score_itf//bazel:py_itf_plugin.bzl", "py_itf_plugin")

py_itf_plugin(
    name = "my_plugin",
    enabled_plugins = ["my_plugin"],
    py_library = "//path/to:my_plugin_lib",
    visibility = ["//visibility:public"],
)
```

Use it in tests:

```starlark
py_itf_test(
    name = "test_custom",
    srcs = ["test.py"],
    plugins = ["//path/to:my_plugin"],
)
```
