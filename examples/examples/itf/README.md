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

# The example application on a container, a DLT target and a QEMU machine

| Test | Target | Shows |
|---|---|---|
| `example_app` | `targets/docker/` by default, `targets/qemu/` when building for QNX (`--config=qemu-integration`) | one test file on two machines, the target picked by a `select()` |
| `dlt` | `targets/dlt/` | a target's DLT logs received by the session; the project's policy starts dlt-daemon |

Each target explicitly lists `examples/itf/targets/policy.py` in YAML `policies:`: readiness checks,
evidence, the dlt-daemon action. The policy is shared by declaration, not discovered from parent directories.
The `itf_target` rules bundle it in `srcs`; YAML remains the source of truth. Loading its contributions does
not trigger the dlt-daemon action absent goals requiring it.

Run from the `examples/` MODULE root; the policy paths are relative to that working directory, not the YAML
parent. Under `bazel run`, `BUILD_WORKING_DIRECTORY` supplies the caller's working directory.
`bazel build //examples/itf:target_docker` compiles a target file without starting anything.
