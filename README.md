<!--
*******************************************************************************
Copyright (c) 2025 Contributors to the Eclipse Foundation
See the NOTICE file(s) distributed with this work for additional
information regarding copyright ownership.
This program and the accompanying materials are made available under the
terms of the Apache License Version 2.0 which is available at
https://www.apache.org/licenses/LICENSE-2.0
SPDX-License-Identifier: Apache-2.0
*******************************************************************************
-->
# Integration Test Framework
This module implements support for running [`pytest`](https://docs.pytest.org/en/latest/contents.html) based tests
for ECUs (Electronic Control Units) in automotive domain.
The Integration Test Framework aims to support ECU testing on real hardware and on simulation (QEMU or QVP) as target.

## Usage
In your `MODULE.bazel` file, add the following line to include the ITF dependency:
```
bazel_dep(name = "itf", version = "0.1.0")
```

In your `.bazelrc` file, add the following line to include ITF configurations:
```
common --registry=https://raw.githubusercontent.com/eclipse-score/bazel_registry/main/
common --registry=https://bcr.bazel.build

build:qemu-integration --config=x86_64-qnx
build:qemu-integration --run_under=@score_itf//scripts:run_under_qemu
build:qemu-integration --test_arg="--qemu"
build:qemu-integration --test_arg="--os=qnx"
```

## Configuration options
Several additional command line options can be added to the execution to customize it.
These are divided into two groups: bazel configs and pytest arguments.

The bazel configs generally influence the build options. These include modifying the bazel `select()` statements, changing the dependencies tree, etc. Available configs are:
- `--config=qemu-integration` - Run ITF for QEMU target. If `--qemu_image` is specified, ITF will automatically start QEMU with the provided image before running the tests.

The Python arguments customize the runtime behavior.
They can be found in [`itf/plugins/base/base_plugin.py`](itf/plugins/base/base_plugin.py) file or displayed by passing `--test_arg="--help"` to any test invocation.
All the options can be passed in command line wrapped in `--test_arg="<...>"` or in `args` parameter of `py_itf_test` macro in `BUILD` file.

Runtime arguments:
* `--target_config` - Path to the target configuration file
* `--dlt_receive_path` - Path to DLT receive binary (Internally provided in `py_itf_test` macro)
* `--ecu` - Target ECU under test
* `--os` - Target Operating System
* `--qemu` - Run tests with QEMU image
* `--qemu_image` - Path to a QEMU image
* `--qvp` - Run tests with QVP simulation
* `--hw` - Run tests against connected HW


## Target configuration file
Target configuration file is a JSON file defining the ECUs under test, their connection parameters, DLT settings, etc.
Target configuration file path can be specified using `--target_config` argument.
An example file for S-CORE QEMU can be found in [`config/target_config.json`](config/target_config.json).

```json
{
    "S_CORE_ECU_QEMU_BRIDGE_NETWORK": {
        "performance_processor": {
            "name": "S_CORE_ECU_QEMU_BRIDGE_NETWORK_PP",
            "ip_address": "192.168.122.76",
            "ext_ip_address": "192.168.122.76",
            "ssh_port": 22,
            "diagnostic_ip_address": "192.168.122.76",
            "diagnostic_address": "0x91",
            "serial_device": "",
            "network_interfaces": [],
            "ecu_name": "s_core_ecu_qemu_bridge_network_pp",
            "data_router_config": {
                "vlan_address": "127.0.0.1",
                "multicast_addresses": []
            },
            "qemu_num_cores": 2,
            "qemu_ram_size": "1G"
        },
        "safety_processor": {
            "name": "S_CORE_ECU_QEMU_BRIDGE_NETWORK_SC",
            "ip_address": "192.168.122.76",
            "diagnostic_ip_address": "192.168.122.76",
            "diagnostic_address": "0x90",
            "serial_device": "",
            "use_doip": true
        },
        "other_processors": {}
    },
    ...
}
```

Target configuration file contains a dictionary of ECUs. Each ECU contains its processors (`performance_processor`, `safety_processor`, `other_processors`).
Each processor contains its connection parameters.

Performance processor: `performance_processor`
* `name` - Name of the processor
* `ip_address` - IP address of the processor
* `ext_ip_address` - External IP address of the processor (for cases where no direct access is possible)
* `ssh_port` - SSH port of the processor
* `diagnostic_ip_address` - IP address for diagnostics communication
* `diagnostic_address` - Diagnostic address of the processor
* `serial_device` - Serial device path if serial connection is used
* `network_interfaces` - List of network interfaces on the processor
* `ecu_name` - Name of the ECU as known on the target system
* `data_router_config` - Configuration for data router
  * `vlan_address` - VLAN address for data router
  * `multicast_addresses` - List of multicast addresses for data router
* `qemu_num_cores` - Number of CPU cores to allocate for QEMU
* `qemu_ram_size` - Amount of RAM to allocate for QEMU
* `use_doip` - Whether to use DoIP for diagnostics communication

Safety processor: `safety_processor`
* `name` - Name of the processor
* `ip_address` - IP address of the processor
* `diagnostic_ip_address` - IP address for diagnostics communication
* `diagnostic_address` - Diagnostic address of the processor
* `serial_device` - Serial device path if serial connection is used
* `use_doip` - Whether to use DoIP for diagnostics communication

Other processors: `other_processors`
* Dictionary of other processors with same parameters as `safety_processor`.

## Bazel
ITF provides a macro `py_itf_test` to simplify the creation of ITF based tests.
BUILD file example:
```python
load("@itf//:defs.bzl", "py_itf_test")

py_itf_test(
    name = "test_ssh_qemu",
    srcs = [
        "test/itf/test_ssh.py",
    ],
    args = [
        "--target_config=$(location target_config.json)",
        "--ecu=s_core_ecu_qemu",
        "--qemu_image=$(location //build:init)",
    ],
    plugins = [
        "itf.plugins.base.base_plugin",
    ],
    data = [
        "//build:init",
        "target_config.json",
    ],
)
```

## Regenerating pip dependencies
```bash
bazel run //:requirements.update
```

## Running tests
```bash
bazel test //test/...
```

Specify additionally:
- `--test_arg="-s"` to get stdout/err from pytest
- `--test_output=all` to get stdout/err from bazel
- `--nocache_test_results` not to cache test runs

## Preparation for testing with QEMU
To run the tests against QEMU target, KVM must be installed.
Following steps are for Ubuntu. See this tutorial: https://help.ubuntu.com/community/KVM/Installation

First, check if your system supports KVM. Run `ls -l /dev/kvm` - if the device is there, your system does support it.

Install necessary packages:
```bash
sudo apt-get install qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils python3-guestfs qemu-utils libguestfs-tools
sudo adduser `id -un` libvirt
sudo adduser `id -un` kvm
```

After the installation, you need to relogin - either reboot or ``` sudo login `id -un` ```.
Verify that the user is in KVM group by running: ``` groups ```.

## Running test against QNX Qemu
ITF can be run against running Qemu defined here https://github.com/eclipse-score/reference_integration/tree/main/qnx_qemu.
Steps:
* Checkout repository https://github.com/eclipse-score/reference_integration
* Run ssh test with qemu started with bridge network
  * Start Qemu with bridge network from `reference_integration/qnx_qemu` folder:
    ```bash
    bazel run --config=x86_64-qnx //:run_qemu
    ```
  * Run ITF test from `itf` folder:
    ```bash
    bazel test //test:test_ssh_bridge_network --test_output=streamed
    ```
  * Note: If it fails, check `IP address set to:` in logs of started Qemu and update IP addresses in `itf/config/target_config.json` for `S_CORE_ECU_QEMU_BRIDGE_NETWORK`
* Run ssh test with qemu started with port forwarding
  * Start Qemu with bridge network from `reference_integration/qnx_qemu` folder:
    ```bash
    bazel run --config=x86_64-qnx //:run_qemu_portforward
    ```
  * Run ITF test from `itf` folder:
    ```bash
    bazel test //test:test_ssh_port_forwarding --test_output=streamed
    ```
* Run ITF test with Qemu started automatically (https://github.com/eclipse-score/reference_integration/blob/main/qnx_qemu/README.md)
  * From `reference_integration/qnx_qemu` folder, run:
    ```bash
    bazel test --config=qemu-integration //:test_ssh_qemu --test_output=streamed
    ```

## Writing tests
Tests are written using `pytest` framework. Tests can utilize various ITF plugins to interact with the target ECU, perform diagnostics, capture logs, etc.

Example test using SSH to connect to the target ECU:
```python
from itf.plugins.com.ssh import execute_command


def test_ssh_with_default_user(target_fixture):
    with target_fixture.sut.ssh() as ssh:
        execute_command(ssh, "echo 'Username:' $USER && uname -a")
```

Main plugin is base plugin which provides common functionality, fixtures and argument parsing.
It should be specified in the `plugins` parameter of `py_itf_test` macro.
```python
    plugins = [
        "itf.plugins.base.base_plugin",
    ],
```

Fixtures provided by base plugin are:
* [`target_fixture`](itf/plugins/base/base_plugin.py#L89) - Provides access to the target ECU under test, its processors, connection methods, etc.
* [`test_config_fixture`](itf/plugins/base/base_plugin.py#L78) - Provides access to the test configuration, command line arguments.
* [`target_config_fixture`](itf/plugins/base/base_plugin.py#L83) - Provides access to the target configuration read from target configuration file.

### Communication with ECU
Main communication with target ECU is done via [`target_fixture`](itf/plugins/base/base_plugin.py#L89).

Usage of `target_fixture` to get performance processor SSH connection:
```python
with target_fixture.sut.performance_processor.ssh() as ssh:
    # Use ssh connection
```

Usage of `target_fixture` to get performance processor SFTP connection:
```python
with target_fixture.sut.performance_processor.sftp() as sftp:
    # Use sftp connection
```

Usage of `target_fixture` to ping performance processor:
```python
target_fixture.sut.performance_processor.ping()
```

Usage of `target_fixture` to check is ping lost of performance processor:
```python
target_fixture.sut.performance_processor.ping_lost()
```

For parameters of above mentioned functionality see [`target_processor.py`](itf/plugins/base/target/processors/target_processor.py).

## Capture DLT messages
By default ITF will start capturing DLT messages from the target ECU's performance processor
when the test starts and stop capturing when the test ends.
Captured DLT messages can be found in `dlt_receive.dlt` which can be found in `bazel-testlogs` folder.

Class [`DltWindow`](itf/plugins/dlt/dlt_window.py) can used in test to capture DLT messages in tests.
```python
dlt = DltWindow(dlt_file="./my_test.dlt")
with dlt.record():
    # Do something which will send DLT messages

# Stop recording
dlt.stop()

# Load captured DLT messages from file
dlt.load()

# Query captured DLT messages to check does it contains expected messages
query_dict = dict(apid=re.compile(r"LOGC"), payload_decoded=re.compile(rf".*{process}\[my_process.*\]:\s+Thread priority set to 70"))
dlt_thread_results = dlt.find(query=query_dict)

# Clear captured messages
dlt.clear()
```
