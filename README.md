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
# Integration Test Framework (ITF)

ITF is a [`pytest`](https://docs.pytest.org/en/latest/contents.html)-based testing framework designed for ECU (Electronic Control Unit) testing in automotive domains. It provides a flexible, plugin-based architecture that enables testing on multiple target environments including Docker containers, QEMU virtual machines, and real hardware.

## Key Features

- **Plugin-Based Architecture**: Modular design with support for Docker, QEMU, DLT, and custom plugins
- **Target Abstraction**: Unified `Target` interface with capability-based system for different test environments
- **Flexible Testing**: Write tests once, run across multiple targets (Docker, QEMU, hardware)
- **Capability System**: Tests can query and adapt based on available target capabilities
- **Bazel Integration**: Seamless integration with Bazel build system via `py_itf_test` macro

## Quick Start

### Installation

Add ITF to your `MODULE.bazel`:
```starlark
bazel_dep(name = "score_itf", version = "0.1.0")
```

Configure your `.bazelrc`:
```
common --registry=https://raw.githubusercontent.com/eclipse-score/bazel_registry/main/
common --registry=https://bcr.bazel.build
```

### Basic Test Example

```python
# test_example.py
def test_docker_exec(target):
    exit_code, output = target.execute("echo 'Hello from target!'")
    assert exit_code == 0
    assert b"Hello from target!" in output
```

### BUILD Configuration

For external consumers, use the `@score_itf` prefix for all loads and plugin references:

```starlark
load("@score_itf//:defs.bzl", "py_itf_test")

py_itf_test(
    name = "test_example",
    srcs = ["test_example.py"],
    args = ["--docker-image=ubuntu:24.04"],
    plugins = ["@score_itf//score/itf/plugins:docker_plugin"],
)
```

## Architecture

### Target System

ITF uses a capability-based target system. The `Target` base class provides a common interface that all target implementations extend:

```python
from score.itf.plugins.core import Target

class MyTarget(Target):
    def __init__(self):
        super().__init__(capabilities={'ssh', 'sftp', 'exec'})
```

Tests can check for capabilities and adapt accordingly:

```python
from score.itf.plugins.core import requires_capabilities

@requires_capabilities("exec")
def test_docker_command(target):
    exit_code, output = target.execute("ls -la")
    assert exit_code == 0

@requires_capabilities("ssh", "sftp")
def test_file_transfer(target):
    with target.ssh() as ssh:
        # SSH operations
        pass
```

### Plugin System

ITF supports modular plugins that extend functionality:

- **`core`**: Basic functionality that is the entry point for plugin extensions and hooks
- **`docker`**: Docker container targets with `exec`, `file_transfer`, and `restart` capabilities
- **`qemu`**: QEMU virtual machine targets with `ssh`, `sftp`, `exec`, `file_transfer`, and `restart` capabilities
- **`dlt`**: DLT (Diagnostic Log and Trace) message capture and analysis

## Writing Tests

### Basic Test Structure

Tests receive a `target` fixture that provides access to the target environment:

```python
def test_basic(target):
    # Use target methods based on capabilities
    if target.has_capability("ssh"):
        with target.ssh() as ssh:
            # Perform SSH operations
            pass
```

### Docker Tests

Docker tests use `target.execute()` which runs commands via Docker's native exec API. This works with any Docker image:

```python
def test_docker_exec(target):
    exit_code, output = target.execute("uname -a")
    assert exit_code == 0
    assert b"Linux" in output
```

BUILD file:
```starlark
py_itf_test(
    name = "test_docker",
    srcs = ["test_docker.py"],
    args = ["--docker-image=ubuntu:24.04"],
    plugins = ["@score_itf//score/itf/plugins:docker_plugin"],
)
```

#### SSH on Docker Targets

If you need SSH access to a Docker container (via `target.ssh()`), the Docker image must have an SSH server installed and running. A plain image like `ubuntu:24.04` will **not** work with `target.ssh()`.

Use an SSH-capable image (e.g. `linuxserver/openssh-server`) and configure credentials via the `docker_configuration` fixture:

```python
import pytest

@pytest.fixture(scope="session")
def docker_configuration():
    return {
        "environment": {
            "PASSWORD_ACCESS": "true",
            "USER_NAME": "score",
            "USER_PASSWORD": "score",
        },
        "command": None,
        "init": False,
    }

def test_ssh_on_docker(target):
    with target.ssh() as ssh:
        exit_code = ssh.execute_command("echo 'Hello via SSH!'")
        assert exit_code == 0
```

```starlark
py_itf_test(
    name = "test_docker_ssh",
    srcs = ["test_docker_ssh.py"],
    args = ["--docker-image=linuxserver/openssh-server:version-10.2_p1-r0"],
    plugins = ["@score_itf//score/itf/plugins:docker_plugin"],
)
```

### QEMU Tests

```python
def test_qemu_ssh(target):
    with target.ssh(username="root", password="") as ssh:
        exit_code = ssh.execute_command("uname -a")
        assert exit_code == 0
```

BUILD file:
```starlark
py_itf_test(
    name = "test_qemu",
    srcs = ["test_qemu.py"],
    args = [
        "--qemu-config=$(location qemu_config.json)",
        "--qemu-image=$(location //path:qemu_image)",
        "--qemu-arch=aarch64",  # or x86_64
    ],
    data = [
        "qemu_config.json",
        "//path:qemu_image",
    ],
    plugins = ["@score_itf//score/itf/plugins:qemu_plugin"],
)
```

QEMU targets are configured using a JSON configuration file passed via `--qemu-config`. The JSON must have a top-level `"qemu"` key. Unknown fields are rejected.

**Bridge networking** (direct guest IP via TAP):

```json
{
    "qemu": {
        "ram_size": 1024,
        "cpu_count": 2,
        "host_qemu_network": {
            "subnet": "169.254.0.0/16",
            "ip_address": "169.254.158.190",
            "mac_address": "52:54:00:12:34:56"
        }
    }
}
```

**Port-forwarding** (user-mode networking via localhost):

```json
{
    "qemu": {
        "ram_size": 1024,
        "cpu_count": 2,
        "host_qemu_network": {
            "subnet": "127.0.0.0/8",
            "ip_address": "127.0.0.1",
            "mac_address": "52:54:00:12:34:56",
            "port_forwarding": [
                {
                    "description": "SSH",
                    "host_port": 2222,
                    "target_port": 22
                }
            ]
        }
    }
}
```

With port-forwarding configured, ITF connects to `127.0.0.1` on the mapped host port for SSH. Without it, it connects directly to the guest IP.

Optional fields (with their defaults):

| Field | Default | Description |
|---|---|---|
| `enable_kvm` | `true` | Enable KVM (currently unused, see KVM section) |
| `kernel_rootfs_folder` | `""` | Folder containing rootfs alongside the kernel |
| `disk_image` | `""` | Path to a qcow2 disk image (created if absent) |
| `startup_timeout` | `60` | Seconds to wait for the guest to boot |
| `logfile` | `""` | Path for QEMU console log output |
| `security_enabled` | `false` | Enable security features |
| `qemu_network` | `null` | Inter-QEMU multicast network (see below) |

The optional `qemu_network` block configures a secondary multicast network for communication between multiple QEMU instances:

```json
"qemu_network": {
    "ip_address": "192.168.116.20",
    "mcast_socket_port": 5432,
    "mcast_socket_mac": "52:54:00:12:34:74"
}
```


### Capability-Based Tests

The `@requires_capabilities` decorator automatically skips tests if the target doesn't support required capabilities:

```python
from score.itf.plugins.core import requires_capabilities

@requires_capabilities("exec")
def test_docker_specific(target):
    # Only runs on targets with 'exec' capability
    target.execute("echo test")

@requires_capabilities("ssh", "sftp")
def test_network_features(target):
    # Only runs on targets with both 'ssh' and 'sftp'
    with target.ssh() as ssh:
        pass
```

## Communication APIs

### SSH Operations

The `Ssh` class provides `execute_command` (returns exit code) and `execute_command_output` (returns exit code, stdout lines, stderr lines) methods. SSH requires a target with an SSH server running (e.g. a Docker image with OpenSSH, or a QEMU VM).

```python
def test_ssh_command(target):
    with target.ssh(username="root", password="") as ssh:
        exit_code = ssh.execute_command("ls -la /tmp")
        assert exit_code == 0

def test_ssh_with_output(target):
    with target.ssh(username="root", password="") as ssh:
        exit_code, stdout_lines, stderr_lines = ssh.execute_command_output("ls -la /tmp")
        assert exit_code == 0
```

> **Note:** For Docker targets, `target.ssh()` connects to the container via SSH on port 2222. Your Docker image must have an SSH server installed and running (e.g. `linuxserver/openssh-server`). If you only need to run commands in a Docker container, use `target.execute()` instead — it uses Docker's native exec API and works with any image.

### SFTP File Transfer

SFTP is available on QEMU targets via `target.sftp()`:

```python
def test_file_transfer(target):
    with target.sftp() as sftp:
        sftp.upload("local_file.txt", "/tmp/remote_file.txt")
        sftp.download("/tmp/remote_file.txt", "downloaded_file.txt")
```

> **Note:** `target.sftp()` is only available on QEMU targets. For Docker targets, use `target.upload()` and `target.download()` instead, which use the Docker API directly.

### Network Testing

Network testing methods are available on QEMU targets:

```python
def test_ping(target):
    # Check if target is reachable
    assert target.ping(timeout=5)

    # Wait until target becomes unreachable (e.g. after restart)
    target.ping_lost(timeout=30, interval=1)
```

> **Note:** `target.ping()` and `target.ping_lost()` are only available on QEMU targets.

## DLT Support

The DLT plugin enables capturing and analyzing Diagnostic Log and Trace messages. `DltWindow` captures DLT messages from a target and allows querying the recorded data:

```python
from score.itf.plugins.dlt.dlt_window import DltWindow
from score.itf.plugins.dlt.dlt_receive import Protocol
import re

def test_with_dlt_capture(target, dlt_config):
    # Create DltWindow to capture DLT messages via UDP
    with DltWindow(
        protocol=Protocol.UDP,
        host_ip="127.0.0.1",
        multicast_ips=["224.0.0.1"],
        print_to_stdout=False,
        binary_path=dlt_config.dlt_receive_path,
    ) as window:
        # Perform operations that generate DLT messages
        with target.ssh() as ssh:
            ssh.execute_command("my_application")
        
        # Access the recorded DLT data
        record = window.record()
        
        # Query for specific DLT messages
        query = {
            "apid": re.compile(r"APP1"),
            "payload": re.compile(r".*Started successfully.*")
        }
        results = record.find(query=query)
        assert len(results) > 0
        
        # Or iterate through all messages
        for frame in record.find():
            if "error" in frame.payload.lower():
                print(f"Error found: {frame.payload}")
```

DLT messages can also be captured with TCP protocol and optional filters:

```python
# TCP connection to specific target
with DltWindow(
    protocol=Protocol.TCP,
    target_ip="192.168.1.100",
    print_to_stdout=True,
    binary_path=dlt_config.dlt_receive_path,
) as window:
    # Operations...
    pass

# With application/context ID filter
with DltWindow(
    protocol=Protocol.UDP,
    host_ip="127.0.0.1",
    multicast_ips=["224.0.0.1"],
    dlt_filter="APPID CTID",  # Filter by APPID and CTID
    binary_path=dlt_config.dlt_receive_path,
) as window:
    # Operations...
    pass
```

### DLT Configuration File

DLT settings can be specified in a JSON configuration file:

```json
{
    "target_ip": "192.168.122.76",
    "host_ip": "192.168.122.1",
    "multicast_ips": [
        "239.255.42.99"
    ]
}
```

This configuration file can be passed to tests via the `--dlt-config` argument in the BUILD file:

```starlark
py_itf_test(
    name = "test_with_dlt",
    srcs = ["test.py"],
    args = [
        "--dlt-config=$(location dlt_config.json)",
    ],
    data = ["dlt_config.json"],
    plugins = ["@score_itf//score/itf/plugins:dlt_plugin", "@score_itf//score/itf/plugins:docker_plugin"],
)
```

## Advanced Features

### Target Lifecycle Management

Control whether targets persist across tests using the `--keep-target` flag:

```bash
# Keep target running between tests (faster, but shared state)
bazel test //test:my_test -- --test_arg="--keep-target"

# Default: Create fresh target for each test
bazel test //test:my_test
```

### Custom Docker Configuration

Override Docker settings in tests by implementing the `docker_configuration` fixture. Supported keys: `environment`, `command`, `init`, `shm_size`, `volumes`.

```python
import pytest

@pytest.fixture
def docker_configuration():
    return {
        "environment": {"MY_VAR": "value"},
        "command": "my-custom-command",
        "init": True,
        "shm_size": "2G",
        "volumes": {"/host/path": {"bind": "/container/path", "mode": "rw"}},
    }

def test_with_custom_docker(target):
    # Uses custom configuration
    pass
```
## Running Tests

### Basic Test Execution

```bash
# Run all tests
bazel test //test/...

# Run specific test
bazel test //test:test_docker

# Show test output
bazel test //test:test_docker --test_output=all

# Show pytest output
bazel test //test:test_docker --test_arg="-s"

# Don't cache test results
bazel test //test:test_docker --nocache_test_results
```

### Docker Tests

```bash
bazel test //test:test_docker \
    --test_arg="--docker-image=ubuntu:24.04"
```

### QEMU Tests

```bash
bazel test //test:test_qemu \
    --test_arg="--qemu-config=qemu_config.json" \
    --test_arg="--qemu-image=/path/to/kernel.img" \
    --test_arg="--qemu-arch=aarch64"
```

## QEMU Setup (Linux)

### Prerequisites

Check KVM support:
```bash
ls -l /dev/kvm
```

If `/dev/kvm` exists, your system supports hardware virtualization.

### Installation (Ubuntu/Debian)

```bash
sudo apt-get install qemu-kvm libvirt-daemon-system \
    libvirt-clients bridge-utils qemu-utils

# Add user to required groups
sudo adduser $(id -un) libvirt
sudo adduser $(id -un) kvm

# Re-login to apply group changes
sudo login $(id -un)

# Verify group membership
groups
```

### Acceleration

| Architecture | Accelerator | Notes |
|---|---|---|
| `x86_64` | TCG (always) | KVM is not used even if `/dev/kvm` is present |
| `aarch64` | QEMU default | No `-accel` flag is passed; QEMU selects TCG |

If `/dev/kvm` exists but is not readable, QEMU startup will abort. Add your user to the `kvm` group to resolve this.

## Development

### Regenerating Dependencies

```bash
bazel run //:requirements.update
```

### Code Formatting

```bash
bazel run //:format.fix
```

### Running Tests During Development

```bash
# Run with verbose output
bazel test //test/... \
    --test_output=all \
    --test_arg="-s" \
    --nocache_test_results
```

## Creating Custom Plugins

Create a custom plugin by implementing the `Target` abstract class and a `target_init` fixture:

```python
# my_plugin.py
import pytest
from score.itf.plugins.core import Target, determine_target_scope

MY_CAPABILITIES = ["custom_feature"]

class MyTarget(Target):
    def __init__(self):
        super().__init__(capabilities=MY_CAPABILITIES)

    def execute(self, command):
        # Implementation specific logic
        pass

    def execute_async(self, binary_path, args=None, cwd="/"):
        # Implementation specific logic
        pass

    def upload(self, local_path, remote_path):
        # Implementation specific logic
        pass

    def download(self, remote_path, local_path):
        # Implementation specific logic
        pass

    def restart(self):
        # Implementation specific logic
        pass

@pytest.fixture(scope=determine_target_scope)
def target_init():
    yield MyTarget()
```

Register the plugin in a BUILD file using `py_itf_plugin`:

```starlark
load("@score_itf//bazel:py_itf_plugin.bzl", "py_itf_plugin")

py_itf_plugin(
    name = "my_plugin",
    enabled_plugins = ["my_plugin"],
    py_library = "//path/to:my_plugin_lib",
    visibility = ["//visibility:public"],
)
```

Use in tests:

```starlark
py_itf_test(
    name = "test_custom",
    srcs = ["test.py"],
    plugins = ["//path/to:my_plugin"],
)
```

## Project Structure

```
score/itf/
├── core/                 # Core ITF functionality
│   ├── com/              # Communication modules (SSH, SFTP)
│   ├── process/          # Process management
│   ├── target/           # Target base class
│   └── utils/            # Utility functions
├── plugins/              # Plugin implementations
│   ├── core.py           # Core plugin with Target and decorators
│   ├── docker.py         # Docker plugin
│   ├── dlt/              # DLT plugin
│   └── qemu/             # QEMU plugin
└── ...
```

## Contributing

Contributions are welcome! Please ensure:
- All tests pass: `bazel test //test/...`
- Code is formatted: `bazel run //:format.fix`
- New features include tests and documentation

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.
