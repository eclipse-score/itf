<!--
*******************************************************************************
Copyright (c) 2026 Contributors to the Eclipse Foundation

See the NOTICE file(s) distributed with this work for additional
information regarding copyright ownership.

This program and the accompanying materials are made available under the
terms of the Apache License Version 2.0 which is available at
https://www.apache.org/licenses/LICENSE-2.0

SPDX-License-Identifier: Apache-2.0
*******************************************************************************
-->

# Migrate from the original plugin API

The compatibility layer (`score/itf/compat`) retains the original plugin entry points, `Target` facade, common
fixtures, options, imports and Bazel labels over the new engine and packs. Most test bodies can continue to run
through it, but compatibility is not exact in every target-specific behavior. Review the differences below
before migrating an existing suite. ITF's legacy tests exercise this layer in `test/integration/legacy`. The
words are defined in the glossary of [the model](../concepts/model.md#the-vocabulary).

How it works: the original options become a target file (`score/itf/compat/targets/`), the session runs it, and
the original fixtures and `Target` methods are served over the composed roles. The packs' classes carry the
original names: `score.itf.core.com.ssh.Ssh` is the ssh pack's session, `Sftp` its SFTP files, `ping` the ping
pack's functions, `DltReceive` and `DltWindow` the dlt pack's recorder.

There is no switch to turn it on. The original entry points are the switch: a test that loads an original plugin
label (or passes its options) runs on the layer, and a test with `py_itf_test(target = ...)` does not. Such a run
says so once, with an `ItfCompatibilityWarning` naming the original plugins it used.

| Original `Target` method | Role of the target file it uses |
|---|---|
| `execute` | `command` |
| `execute_async`, `wrap_exec` | `process` |
| `upload`, `download` | `files` |
| `restart` | `platform` |
| `ssh()`, `sftp()`, `ping()`, `ping_lost()` | `endpoint` and `credentials`; each call opens a new connection, as before |

A project's own target file serves the original methods when it uses these role names: pass `--itf-target` beside
the original plugin labels and the old tests run on it, before any of them changes.

## Choose transports independently

Role names describe what tests use, not the transport. The compatibility `--docker-ssh` preset chooses
SFTP for `files`; it does not restrict a project's own target file. For example, SSH commands and shell
access can coexist with Docker-native file copying:

```yaml
packs:
    docker: score.itf.packs.docker.plugin
    ssh: score.itf.packs.ssh.plugin
    net: score.itf.packs.net.plugin
capabilities:
    platform:
        factory: docker.platform
        with:
            image: ${SSH_IMAGE}
            ports: 2222/tcp
    endpoint:
        factory: docker.endpoint
        with:
            port: 2222
    credentials:
        factory: net.password
        with:
            user: ${SSH_USER}
            password: ${SSH_PASSWORD}
    shell: ssh.shell
    command: ssh.exec
    process: ssh.process
    files: docker.files
goals:
    - platform.up
    - shell.open
relations:
    - state: shell.open
      after:
          - platform.up
```

The image must run an SSH server on container port 2222 with the configured credentials. Change only
`files: docker.files` to `files: ssh.files` to transfer over SFTP instead. Likewise, `command` and `process`
can independently select `docker.exec`/`docker.process` or `ssh.exec`/`ssh.process`. Any combination is
supported when its provider dependencies and readiness states are supplied; Docker providers require
a Docker platform, while SSH providers require a reachable endpoint, credentials and an open shell.
Multiple providers of the same kind require explicit `bind:` wiring when dependency selection is ambiguous.

The `files.transfer` contract requires both direct calls and context-managed use for every provider:

```python
with target.files as files:
    files.upload(local_path, remote_path)
    files.download(remote_path, downloaded_path)
```

SFTP opens and closes a transfer channel; Docker and localhost need no persistent transfer channel, so their
context managers return the provider and perform no cleanup. Context exit must not close the shared SSH shell
or owning platform, must not suppress exceptions, and must leave the provider usable afterwards. Mandatory
conformance checks verify identity, transfer operations, exception propagation and reuse for every provider.
This tightens the draft version-1 contract; third-party providers must implement both context methods too.
Consumers that use `with` declare `__enter__` and `__exit__` in their own Protocol, so planning/preflight
checks the selected provider before execution. Python's `AbstractContextManager` recognizes provider types;
the published shape retains their method signatures, and conformance checks their runtime behavior.

Both providers preserve file content, create destination directories, and reject missing upload sources
with `FileNotFoundError`. Spaces and shell characters in absolute remote paths are supported; a local output
may be a bare filename or a nested path. Use absolute remote paths for portable behavior: relative paths
depend on the backend's working directory. File ownership, mode and timestamp preservation are not common
guarantees, and access is subject to Docker authority or the SSH user's permissions. SFTP management methods
such as `listdir`, `stat` and directory transfers remain optional extensions: declare the API your test needs
with `@itf.requires("files", shape=...)` rather than assuming every `files` provider has them.

## Three ways to run tests on ITF

| You have | Run them | Example |
|---|---|---|
| tests on ITF's original API (`docker_plugin`, `--docker-image`, `target.execute`) | **common entry points retained**: the compatibility layer (`score/itf/compat`) serves the original API, with the differences above | `test/integration/legacy` |
| tests on your project's own target API | **a target file plus a facade**: `score.itf.Facade` keeps your class over the target file's roles; the compatibility layer is not involved | `examples/examples/facade`, a step-by-step tutorial |
| new tests | **the new API**: `itf_target`, `py_itf_test(target = ...)`, `@itf.requires("<role>")`, `target.<role>` | `test/integration`, `examples/examples/itf`, `examples/examples/starter` |

The middle way also works for the original API: pass `--itf-target` beside the original plugin labels, and the old
tests run on the project's own target file before any of them changes.

## Keeping your own target API: facades

A project that ports its own framework to ITF keeps its test cases as they are and changes only what is under
them. Its target class becomes an `itf.Facade`: the methods it always had, written over the roles of a target file,
served as `target` from `conftest.py`. Every other name reaches ITF's target, so new tests use `target.command` on
the same object. The facade is part of ITF's core, not of the compatibility layer, so it stays when that layer is
removed.

```python
import pytest
import score.itf as itf


class Ecu(itf.Facade):
    CAPABILITIES = {"exec": ("command",), "flash": ("command", "files")}

    def run(self, cmd):
        code, output = self.role("command").exec(cmd)
        return code, output.decode()

    def push(self, local_path, remote_path):
        self.role("files").upload(local_path, remote_path)


@pytest.fixture(scope="session")
def target(target):  # in conftest.py: the tests' target is the facade over ITF's
    return Ecu(target)
```

`role(name)` names the role a method needs, and fails with what the target file has instead. `CAPABILITIES`
answers `has_capability(...)` from the roles present. The original ITF `Target` API is one such facade
(`score.itf.compat.legacy`). The tutorial in `examples/examples/facade` takes a project through it step by step.

## Moving at your own pace

1. Upgrade. Common original and new role APIs can coexist in one suite through the compatibility facade; check the
    differences above before relying on backend-specific behavior.
2. `itf compat report tests/ BUILD`: every original name the suite uses, with file, line and replacement.
3. `itf compat target --docker-image=... --out targets/`: the target file the original options make, with its
   policy and a `.env.example`; give it to an `itf_target` and switch the tests to `py_itf_test(target = ...)`.
4. Move tests one by one to `@itf.requires("<role>")` and `target.<role>`, using the mapping below, until the
   report is empty.

Differences seen through the layer:
- With QEMU, DLT recording starts after the machine has booted.
- `DltWindow.record().find()` returns an empty list when nothing was captured; the original raised python-dlt's
    `OSError: DLT TRACE FILE IS EMPTY`.
- `DockerTarget.ssh()` connects to container port 2222, as before, through its published host port. SSH roles (`endpoint`,
    `credentials`, `shell`) are opt-in with `--docker-ssh`; the image must actually run an SSH server. With this
    option, `files` uses SFTP (`ssh.files`) instead of Docker-native copying; there is no separate `sftp` role.
- `docker_configuration` keys the platform names (`command`, `init`, `environment`, `volumes`, `ports`,
    `shm_size`, `privileged`, `cap_add`, `devices`, `network_mode`) set the platform; every other key goes to
    the Docker SDK, as the original plugin passed it to `containers.run`. `docker_sdk_kwargs` gives SDK arguments
    explicitly (a JSON object string, or a dict in the fixture). Options ITF manages itself (the container name,
    its network and port bindings, auto-remove) are refused. Option details are in
    `score/itf/packs/docker/README.md`, under “Additional Docker SDK Arguments”.
- Native `target.command.exec()` returns `(exit_code, output)`; the legacy `DockerTarget.execute()` retains Docker
    SDK's `ExecResult` attributes.
- Command timeouts are backend-specific. `docker.exec`'s timeout bounds the process wait after exec startup,
    not the full Python call. On expiry it synchronously tries to stop that command and raises `TimeoutError`,
    leaving the container running. Docker cancellation sends another exec and polls at one-second intervals,
    up to five times before escalating to `SIGKILL`; daemon/API latency can add further delay. See the
    “Command Timeout and Cancellation” section in `score/itf/packs/docker/README.md` for the inherited behavior.
- Legacy QEMU module paths (`qemu_process`, `qemu_target()`, `QemuAsyncProcess`, `boot`, `checks`) and the session
    `config` fixture are retained through adapters backed by `Session`, `qemu.platform`, and the SSH pack. They no
    longer create a standalone QEMU process outside ITF's planner and cleanup lifecycle.
- In pytest runs, `platform.up`, `network.reachable`, and `shell.open` are target-file goals with probes. The
    compatibility policy's `itf_verify` hook checks SFTP after those goals hold; `pre_tests_phase` remains available
    for callers that invoke the old helper directly.
- `QemuTarget.guest_panicked` is retained; the new API exposes the same state on `target.platform`.
- `boot_until_ready` and `pre_tests_phase` module paths remain available as compatibility helpers; automatic pytest
    startup uses the session's configured goals/probes and `itf_verify` hook instead.
- The compatibility layer's `target_init` hook is preserved through the original core plugin import path.
- Run files go to the run directory at the chosen artifact level.
- Over SSH (QEMU), `target.execute` returns stderr after stdout, as the docker target always did.

## Mapping

| Original | New |
|---|---|
| `plugins = [".../plugins:docker_plugin"]`, `--docker-image=X` | `packs = ["//score/itf/packs/docker"]` on the `itf_target`; `platform: factory: docker.platform` with `image: X` in `with:` (or in an override file) |
| `--docker-image-bootstrap=$(location :load)` | `with: bootstrap: ${LOAD}` with `env = {"LOAD": "$(location :load)"}` |
| `docker_configuration` fixture | the platform's settings: `environment`, `command`, `init`, `shm_size`, `volumes` (strings), `ports` |
| `--qemu-config/--qemu-kernel/--qemu-rootfs/--qemu-disk` | `qemu.platform` with `config_file`, `kernel`, `rootfs`, `disk` |
| `--qemu-boot-attempts=N` | `--itf-bring-up-attempts=N`: a guest panic stops QEMU, and bring-up plans the boot again (the layer passes the larger of the two, so 3 by default) |
| `--qemu-async-new-connection` | Compatibility-only opt-in: a dedicated SSH connection per async process. By default, `execute_async` uses the target's `process` role and shared shell, with a separate channel per process. |
| `target.execute(cmd)` | `target.command.exec(cmd)`, the same `(int, bytes)` (`command: docker.exec` or `ssh.exec`) |
| `target.execute_async` / `wrap_exec` | `target.process.spawn(...)` / `target.process.wrap_exec(...)` |
| `target.upload` / `download` | `target.files.upload` / `download` (`files: docker.files` or `ssh.files`, which is SFTP) |
| `target.restart()` | `target.platform.restart()` then `session.reach(...)`, or `session.renew("platform")` (`discard` then reach) |
| `target.ssh()` | `target.shell` (`shell: ssh.shell`): the same `Ssh`, `execute_command_output` and all |
| `target.sftp()` | `target.files` with `files: ssh.files`: the same `Sftp` |
| `target.ping()` / `ping_lost()` | `target.ping.ping()` / `ping_lost()` (`ping: ping.ping`) |
| `target.get_ip()` / `get_gateway()` | `target.platform.ip()` / `gateway()` (docker) |
| `@requires_capabilities("exec")` | `@itf.requires("command")` |
| `DltReceive` / `DltWindow` | the same classes from `score.itf.packs.dlt.receive`, or a role: `logs: dlt.receive` |
| `dlt_on_target` fixture | `dlt_on_target: dlt.on_target` (binds `files` and `process`): `target.dlt_on_target.start("tcp")` |

`test/integration/legacy` (ITF's original tests on the layer) and `test/integration` (the same ground in the new API) show both
side by side.
