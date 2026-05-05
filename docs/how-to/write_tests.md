# Write Tests

This guide covers how to write tests for the three main target types: Docker,
QEMU, and capability-based tests.

## Docker tests

Docker tests use `target.execute()` which runs commands via the Docker native
exec API. Any Docker image works — no SSH server required.

```python
def test_exec(target):
    exit_code, output = target.execute("uname -a")
    assert exit_code == 0
    assert b"Linux" in output
```

`BUILD`:

```starlark
load("@score_itf//:defs.bzl", "py_itf_test")

py_itf_test(
    name = "test_exec",
    srcs = ["test_exec.py"],
    args = ["--docker-image=ubuntu:24.04"],
    plugins = ["@score_itf//score/itf/plugins:docker_plugin"],
)
```

### SSH on Docker targets

> **`ubuntu:24.04` does not work with `target.ssh()`.**
> `target.ssh()` makes a real SSH connection to port 2222 of the container
> with username/password authentication. A plain Ubuntu image has no SSH
> server, so the connection will always fail. Use `target.execute()` instead
> (shown above) unless you specifically need SSH.

If you do need SSH, use an image that runs an SSH server
(e.g. `linuxserver/openssh-server`) and supply credentials via the
`docker_configuration` fixture:

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

def test_ssh(target):
    with target.ssh() as ssh:
        # execute_command is a method on the Ssh object — no separate import needed
        exit_code = ssh.execute_command("whoami")
        assert exit_code == 0
```

`BUILD`:

```starlark
py_itf_test(
    name = "test_ssh",
    srcs = ["test_ssh.py"],
    args = ["--docker-image=linuxserver/openssh-server:version-10.2_p1-r0"],
    plugins = ["@score_itf//score/itf/plugins:docker_plugin"],
)
```

### Custom Docker configuration

Override Docker settings per test by implementing `docker_configuration`.
Supported keys: `environment`, `command`, `init`, `shm_size`, `volumes`.

```python
import pytest

@pytest.fixture
def docker_configuration():
    return {
        "environment": {"MY_VAR": "hello"},
        "shm_size": "2G",
        "volumes": {"/host/path": {"bind": "/container/path", "mode": "rw"}},
    }
```

## QEMU tests

QEMU targets expose SSH and SFTP capabilities, and optionally network testing
via `target.ping()`.

```python
def test_qemu_ssh(target):
    with target.ssh(username="root", password="") as ssh:
        exit_code = ssh.execute_command("uname -a")
        assert exit_code == 0

def test_file_transfer(target):
    with target.sftp() as sftp:
        sftp.upload("local.txt", "/tmp/remote.txt")
        sftp.download("/tmp/remote.txt", "downloaded.txt")
```

`BUILD`:

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

QEMU configuration file (`qemu_config.json`):

```json
{
    "networks": [
        {
            "name": "tap0",
            "ip_address": "169.254.158.190",
            "gateway": "169.254.21.88"
        }
    ],
    "ssh_port": 22,
    "qemu_num_cores": 2,
    "qemu_ram_size": "1G"
}
```

## Capability-based tests

The `@requires_capabilities` decorator automatically skips tests if the target
does not provide the listed capabilities.

```python
from score.itf.plugins.core import requires_capabilities

@requires_capabilities("exec")
def test_docker_only(target):
    # Skipped automatically on targets without 'exec'
    exit_code, output = target.execute("ls /tmp")
    assert exit_code == 0

@requires_capabilities("ssh", "sftp")
def test_network_features(target):
    # Only runs on targets that have both 'ssh' and 'sftp'
    with target.ssh() as ssh:
        ssh.execute_command("echo ok")
```

## Target lifecycle: `--keep-target`

By default, ITF creates a fresh target for each test function. Pass
`--keep-target` to keep the same target running across all tests in a suite
(faster, but tests share state):

```bash
bazel test //test:my_test --test_arg=--keep-target
```
