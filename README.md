# ITF - Integration Testing Framework

This module implements support for running [pytest](https://docs.pytest.org/en/latest/contents.html) based tests.

## Usage
MODULE.bazel
```
bazel_dep(name = "itf", version = "0.1")
```

BUILD
```
load("@itf//:defs.bzl", "py_itf_test")

py_itf_test(
    name = "test_my_first_check",
    srcs = [
        "test_my_first_check.py"
    ],
    plugins = [
        # Specify optional plugins, ex:
        "itf.plugins.docker",
    ]
    args = [
        # Specify optional arguments, ex:
        "--docker-image=alpine:latest",
    ]
)
```

## Development

### Regenerating pip dependencies
```
$ bazel run //:requirements.update
```

### Running test
```
$ bazel test //test/...
```

Specify additionally:
- ```--test_arg="-s"``` to get stdout/err from pytest
- ```--test_output=all``` to get stdout/err from bazel
- ```--nocache_test_results``` not to cache test runs

### Running test against QNX Qemu
ITF can be run against running Qemu defined here https://github.com/eclipse-score/reference_integration/tree/main/qnx_qemu.
Steps:
* Checkout repository https://github.com/eclipse-score/reference_integration
* Run ssh test with qemu started with bridge network
  * Start Qemu with bridge network from `reference_integration/qnx_qemu` folder:
    ```
    $ bazel run --config=x86_64-qnx //:run_qemu
    ```
  * Run ITF test from `itf` folder:
    ```
    $ bazel test //test:test_ssh_bridge_network --test_output=streamed
    ```
  * Note: If it fails, check `IP address set to:` in logs of started Qemu and update IP addresses in `itf/config/target_config.json` for `S_CORE_ECU_QEMU_BRIDGE_NETWORK`
* Run ssh test with qemu started with port forwarding
  * Start Qemu with bridge network from `reference_integration/qnx_qemu` folder:
    ```
    $ bazel run --config=x86_64-qnx //:run_qemu_portforward
    ```
  * Run ITF test from `itf` folder:
    ```
    $ bazel test //test:test_ssh_port_forwarding --test_output=streamed
    ```
