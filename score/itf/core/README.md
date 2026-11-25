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

# score.itf.core: the engine

The core plans and runs a target from what parts declare. It knows no technology (a gate test keeps docker, ssh,
dlt and the rest out of it) and no project. `import score.itf as itf` is its public API, listed in `__init__.py`;
everything else here is internal.

| Path | Holds |
|---|---|
| `session.py` | `Session`: one catalog, one target file, one plan, one bring-up; `reach`, `discard`, `renew`, `probe` while tests run |
| `target_handle.py` | the `target` tests use: roles as attributes, device scopes as `target.<scope>` |
| `gating.py` | `@itf.requires` and the decision, per test, from the plan |
| `facade.py` | `itf.Facade`: a project's own target API over the roles |
| `artifacts.py` | what a run leaves in its run directory, also after a failure |
| `engine/` | registration, the plan's inputs and outputs, bring-up, teardown, evidence, logging, secrets ([README](engine/README.md)) |
| `frontends/` | the target file format (`target_file.py`) and which target file a run uses (`target_source.py`) |
| `adapters/` | the pytest adapter (`adapters/pytest`) and the contract definitions a session may be handed |
| `octo/` | the planner: claims in, a plan or diagnostics out, standard library only ([README](octo/README.md)) |
| `process/` | process handles shared by the core and every pack (`AsyncProcess`, `ProcessWrapper`, `WrappedProcess`) |
| `com/`, `target/`, `utils/` | ITF's original module paths, kept for existing tests: re-exports only (`score/itf/compat`) |

How a run flows: the frontend reads the target file; `engine/registry.py` and `engine/publish.py` turn the loaded
packs into a catalog; OCTO plans; `engine/realize.py` builds roles lazily; `engine/bringup.py` probes and runs the
actions; `engine/close.py` verifies, tears down and unwinds; `engine/evidence.py` records it. The principles are in
`docs/concepts/manifesto.md`, the vocabulary in `docs/concepts/model.md`.
