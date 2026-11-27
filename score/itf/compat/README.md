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

# score.itf.compat: ITF's original API, served by the new engine

The compatibility layer retains the original plugin entry points, common options, fixtures, imports and Bazel
labels over the new session, planner and packs. Most test bodies can continue to run through it, but a few
target-specific options and behaviors differ; see [the migration guide](../../docs/how-to/migrate.md) before
relying on exact legacy behavior. This package is the whole layer, so it can be measured (`itf compat report`)
and removed in one change when its deprecation period ends.

| Path | Holds |
|---|---|
| `plugins/` | the original pytest plugins (core, docker, qemu, dlt, core dump): their options, fixtures and `target_init` |
| `plugins/targets.py` | which shipped target file the original options select, and the `${NAME}` values they fill |
| `targets/` | those target files (`docker`, `docker_ssh`, `qemu`, with and without DLT) and their policy, compiled at build time |
| `legacy.py` | `LegacyTarget`, `DockerTarget`, `QemuTarget`: the original methods over the roles, as an `itf.Facade` |
| `target.py` | the original `Target` and `UnsupportedTarget` base classes, for a project's own target plugins |
| `utils/` | the original small helpers |
| `tools.py` | `itf compat report` and `itf compat target` |

How it switches on: through the entry points a project already uses (the original plugin labels and options),
never through a setting; `py_itf_test(target = ...)` does not load it. A run on it warns once
(`ItfCompatibilityWarning`). The original module paths (`score/itf/plugins`, `score/itf/core/com`, `.target`,
`.utils`) only re-export from here and from the packs; `//test/integration/compat:shims_test` checks that.

As the original plugin, the compatibility Docker target has no SSH capability: `DockerTarget.ssh()` opens a
connection to container port 2222 (`score`/`score` unless given) without any SSH role, reached as
`docker.endpoint` reaches it: the published host port (the compatibility target publishes 2222), else the
container's IP, which a rootless engine does not route.
`--docker-ssh` (with an image that runs an SSH server) adds SSH roles instead: `target.ssh()` then uses the
target file's endpoint and login, `files` uses `ssh.files` (SFTP) instead of Docker-native copying, and
`requires_capabilities("ssh")` holds. There is no separate `sftp` role; `target.sftp()` remains available.

QEMU `execute_async` shares the composed target's process role and SSH connection by default, using an
independent channel per process. `--qemu-async-new-connection` restores the original dedicated connection
per process, closed after successful `wait()` or `stop()`. Python callers can use
`QemuTarget(handle, async_new_connection=True)` or set `qemu_async_new_connection=True` on the configuration
passed to `qemu_target()`. Closing or replacing a shared connection invalidates its active process channels;
neither mode guarantees remote process survival or recovery after a guest reboot or connection loss.

`test/integration/legacy` is ITF's integration suite from main, byte for byte (`tools/legacy_unchanged.py`
checks it), run through this layer; `test/integration/compat` tests what the layer adds. The facade
mechanism is not here but in the core (`itf.Facade`), so it stays when this layer goes. Migration: `docs/how-to/migrate.md`.
