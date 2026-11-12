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

# Tools

| Path | Does |
|---|---|
| `format/` | `bazel run //:format.fix` and the `format.check` tests (ruff, buildifier) |
| `gates/` | the words the core and OCTO may not contain, read by `//test/core:gates_test` |
| `benchmark/` | planning time and memory per phase, against thresholds ([README](benchmark/README.md)) |
| `contract_rules.yaml` | ITF's own contract rules, enforced in CI by `itf contracts check --rules` |
| `coverage_summary.py` | the per-area coverage table CI writes from `bazel coverage` |
| `qnx_credential_helper.py` | the credential helper for QNX downloads (`--config=x86_64-qnx`) |
