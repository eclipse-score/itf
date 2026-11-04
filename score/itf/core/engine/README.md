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

# score.itf.core.engine

The parts of a session between the target file and the tests. Each module has one job; `session.py` composes them.

| Module | Job |
|---|---|
| `publish.py` | `@capability` and `@state`: what a part declares (its contract, slots, settings, probe) |
| `registry.py` | which modules a session registers, their origin, and the rule that packs never import each other |
| `packs.py` | loading a pack from a label: the target file's `packs:`, `score.itf.packs.<name>`, or an entry point |
| `metadata.py` | a pack's `pack.yaml` |
| `config.py` | settings schemas from a factory's `config` dataclass, validated without side effects |
| `scopes.py` | the root scope and the `scope.role` reference syntax |
| `realize.py` | lazy realization: a role is built when first fetched, torn down in reverse |
| `bringup.py` | probe first, then run the actions a plan needs; reuse what already holds |
| `close.py` | `itf_verify` checks, `itf_teardown` hooks, unwind from observed state |
| `hooks.py` | ITF's two pluggy hooks (`itf_verify`, `itf_teardown`); hookwrappers are refused |
| `assumptions.py` | who asserted an assumed state, and why |
| `render.py`, `labels.py`, `failure.py` | the words a person reads: diagnostics, role labels, the failure report |
| `report.py` | the plan as one HTML page |
| `evidence.py` | the run's record (`evidence.json`) and its page (`evidence.html`), and the summary over runs |
| `log.py` | structured logging under `score.itf.core` |
| `secrets.py` | masking sensitive settings in every log, report and failure |
| `yaml_text.py` | the one YAML loader |
