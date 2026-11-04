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

# The `itf` command line

Everything ITF does to a target file, from a terminal or a pipeline: check it, read its plan, draw it, bring it up
by hand, run its tests, and look after the contracts and the move from the original API. The same session and the
same planner as the pytest adapter, so what `itf plan` shows is what a test run does.

## Running it

```bash
bazel run //score/itf/cli:itf -- <command> ...   # in this repository, or any project that depends on score_itf
itf <command> ...                                 # after `pip install`
```

Under `bazel run`, paths are relative to the directory you ran it from, as without Bazel (the CLI changes to
`BUILD_WORKING_DIRECTORY`). A target file is found as for a test run when none is given: `ITF_TARGET`, then
`itf_target` in `pytest.ini`, then `[tool.itf] target` in `pyproject.toml`. Override files come with `--override`
(repeatable) or `ITF_OVERRIDE`. A `${NAME}` a target file reads comes from the environment, else a `.env` beside it.

## Commands

| Command | Does | Touches |
|---|---|---|
| `itf validate [target]` | compiles the target file through both gates; exit 1 with what is wrong and how to fix it | nothing |
| `itf plan [target] [--json] [--output FILE]` | which factory fills each role, which actions run in which order | nothing |
| `itf graph [target] [--kind topology\|sequence\|both]` | the wiring and the bring-up sequence, as Mermaid | nothing |
| `itf diff OLD.json NEW.json` | compares two plans (`itf plan --json`); exit 1 when they differ | nothing |
| `itf doctor [target]` | checks what the target file's packs need on this host; lists what it cannot check | reads the host |
| `itf up [target] [--fresh] [--detach]` | brings the target up and opens a Python console on it; leaving the console takes it down. `--detach` leaves it running | brings it up |
| `itf down [target]` | takes down what the probes observe, for factories that can observe what exists | takes it down |
| `itf test [target] [--override FILE] [-- pytest args]` | runs pytest on the target file, as `py_itf_test` does | brings it up |
| `itf evidence RUN_DIR [--output FILE]` | the report of a finished run (`evidence.html`); `--output` for read-only run directories such as Bazel's | nothing |
| `itf evidence --summary RUN_DIR...` | slowest probes, probes that were false, failing steps, across runs | nothing |
| `itf contracts map [target...] [--format text\|json\|mermaid\|html] [--output FILE]` | every contract in use: who offers it, who needs it, which tests ask for it, disagreements | nothing |
| `itf contracts reference --output FILE` | the Markdown reference of the defined contracts | nothing |
| `itf contracts new NAME --from-usage [target...]` | a definition skeleton from the shapes in use | nothing |
| `itf contracts check --rules FILE [target...]` | enforces a project's contract rules; exit 1 on violations | nothing |
| `itf compat report [paths...]` | every use of the original API in test files and BUILD files, with its replacement | nothing |
| `itf compat target --docker-image=... \| --qemu-config=... [--dlt] --out DIR` | writes the target file the original options make, with a policy and a `.env.example` | nothing |

Commands that start nothing run anywhere: on a laptop without a container engine, in a review, in CI before
any machine exists. `validate`, `plan`, `graph`, `diff` and the contract commands are the ones to wire into
reviews.

## Examples

```bash
itf validate test/integration/targets/localhost.itf.yaml
itf plan --json --output new.plan.json targets/ecu/ecu.itf.yaml && itf diff old.plan.json new.plan.json
itf graph --kind sequence targets/ecu/ecu.itf.yaml > bringup.md
itf doctor targets/ecu/ecu.itf.yaml
itf up targets/ecu/ecu.itf.yaml                    # then: target.command.exec("uname -a")
itf test targets/ecu/ecu.itf.yaml -- -k boot -x
itf evidence bazel-testlogs/test/ecu/test.outputs/itf-run --output evidence.html
itf compat report tests/ BUILD                     # what is left to migrate
```

## Code

| Module | Holds |
|---|---|
| `main.py` | the parser, target file discovery and the lifecycle commands |
| `doctor.py` | host checks, and the `pack.yaml` prerequisites they cover |
| `graph.py` | the Mermaid drawings |
| `contracts_cmd.py`, `compat_cmd.py` | `itf contracts` and `itf compat` |

The commands are thin: they build a `Session` (or read a plan) and print. Behaviour belongs in the core or a pack.
