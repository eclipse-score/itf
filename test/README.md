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

# Tests

`bazel test //...` runs everything that needs no QEMU machine; `bazel coverage //...` does the same with line
coverage of `score/itf`. Container tests need Docker or Podman (`DOCKER_HOST`).

| Path | Tests |
|---|---|
| `core/` | the engine (`itf/`), the planner (`octo/`), the shipped kinds (`kinds/`), and the gates that keep the core free of technology words (`gates/`) |
| `packs/` | each pack without hardware: parts, settings, the original classes, the generated pages (`catalog/`) |
| `contracts/` | the contract library: map, inventory, renderers, definitions |
| `cli/` | every `itf` command, on fixture target files |
| `plans/` | target files compiled through `itf_target`, as a project's are |
| `integration/` | one suite on many target files, in the new API; `integration/legacy/` is ITF's original tests, unchanged, on the compatibility layer ([README](integration/README.md)) |
| `pytest_plugins/` | the requirement attribute plugin |
| `tools/` | the planning benchmark |
| `resources/` | images, QEMU configurations and disks the integration tests use |
