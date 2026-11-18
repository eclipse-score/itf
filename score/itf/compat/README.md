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

Tests written for the original plugins and `Target` run unchanged: the original options, fixtures, imports and
Bazel labels work, over the same session, planner and packs as the new API. This package is the whole layer, so it
can be measured (`itf compat report`) and removed in one change when its deprecation period ends.

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
`.utils`) only re-export from here and from the packs; `//test/integration/legacy:shims_test` checks that.

The compatibility Docker target does not claim SSH/SFTP merely because port 2222 is exposed. Use
`--docker-ssh` with `--docker-image` when that image actually runs an SSH server; the legacy
`requires_capabilities("ssh")` decorator then skips SSH-only cases on Docker images without SSH roles.

Proof: `test/integration/legacy` runs ITF's tests from `main` byte-identical, with `main`'s BUILD file. The facade
mechanism is not here but in the core (`itf.Facade`), so it stays when this layer goes. Migration: `docs/how-to/migrate.md`.
