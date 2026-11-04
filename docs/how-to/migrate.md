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

Tests written for the original API run **unchanged**: the compatibility layer (`score/itf/compat`) serves the
original plugins (`docker_plugin`, `qemu_plugin`, `dlt_plugin`, `core_dump_plugin`), the `Target` class, their
fixtures, options, imports and Bazel labels over the new engine and the packs. An existing `BUILD` file with
`py_itf_test(plugins = [...], args = ["--docker-image=..."])` keeps working. ITF's own original tests run unchanged
against it in `test/integration/legacy`. The words are defined in the glossary of [the model](../concepts/model.md#the-vocabulary).

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

## Three ways to run tests on ITF

| You have | Run them | Example |
|---|---|---|
| tests on ITF's original API (`docker_plugin`, `--docker-image`, `target.execute`) | **unchanged, BUILD files included**: the compatibility layer (`score/itf/compat`) serves the original API | `test/integration/legacy` |
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

1. Upgrade. Nothing changes; old and new tests may live in one suite (`target.command` works on the old
   `target` too).
2. `itf compat report tests/ BUILD`: every original name the suite uses, with file, line and replacement.
3. `itf compat target --docker-image=... --out targets/`: the target file the original options make, with its
   policy and a `.env.example`; give it to an `itf_target` and switch the tests to `py_itf_test(target = ...)`.
4. Move tests one by one to `@itf.requires("<role>")` and `target.<role>`, using the mapping below, until the
   report is empty.

Differences seen through the layer:
- With QEMU, DLT recording starts after the machine has booted.
- `docker_configuration` takes the keys the platform role has (`command`, `init`, `environment`, `volumes`,
  `shm_size`, `privileged`); another key is an error that names it, where the original plugin passed it to Docker.
- Run files go to the run directory at the chosen artifact level.
- `qemu_process`, `checks` and the original plugins' private helpers are not served.
- Over SSH (QEMU), `target.execute` returns stderr after stdout, as the docker target always did.

## Mapping

| Original | New |
|---|---|
| `plugins = [".../plugins:docker_plugin"]`, `--docker-image=X` | `packs = ["//score/itf/packs/docker"]` on the `itf_target`; `platform: factory: docker.platform` with `image: X` in `with:` (or in an override file) |
| `--docker-image-bootstrap=$(location :load)` | `with: bootstrap: ${LOAD}` with `env = {"LOAD": "$(location :load)"}` |
| `docker_configuration` fixture | the platform's settings: `environment`, `command`, `init`, `shm_size`, `volumes` (strings), `ports` |
| `--qemu-config/--qemu-kernel/--qemu-rootfs/--qemu-disk` | `qemu.platform` with `config_file`, `kernel`, `rootfs`, `disk` |
| `--qemu-boot-attempts=N` | `--itf-bring-up-attempts=N`: a guest panic stops QEMU, and bring-up plans the boot again (the layer passes the larger of the two, so 3 by default) |
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
