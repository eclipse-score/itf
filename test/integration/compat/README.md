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

# Compatibility layer tests

ITF's integration tests from main live in `../legacy`, byte for byte, BUILD file included. They run against the
compatibility layer (`score/itf/compat`) through the original labels, options and fixtures.
`python3 tools/legacy_unchanged.py` fails when any file there differs from main or a file is added, so the layer
cannot pass by editing the tests it must keep working. `test/integration/README.md` maps those tests to the
native suites.

This directory tests what the layer adds or must guarantee beyond those tests:

| Target | What it checks |
|---|---|
| `shims_test` | every module of the original paths (`score.itf.plugins`, `score.itf.core.com`, `.target`, `.utils`) only re-exports |
| `layer_test` | the original target classes over the roles of a composed target, without a container |
| `test_docker_configuration` | `docker_configuration` keys the platform does not name reach the Docker SDK, as on main, and so does `docker_sdk_kwargs` |
| `test_docker_ssh` | `--docker-ssh`: files over SFTP, `target.ssh()` with the target file's endpoint and login |

`../legacy:test_dlt` needs multicast between host and container, which a rootless engine does not route.
