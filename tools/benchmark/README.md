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

# Planning benchmark

`plan_bench` measures how long ITF and OCTO take to plan a target file, and how much memory they use. Planning is
what `itf validate`, `itf plan`, the Bazel compile step of an `itf_target` and pytest collection do. Nothing is
brought up: how long a bring-up takes depends on each part's own work, so it is not measured here.

## Run it

With Bazel, from the repository root:

```
bazel run //tools/benchmark:plan_bench -- test/integration/targets/localhost.itf.yaml
bazel run //tools/benchmark:plan_bench -- --scale scopes,chain,deep,wide --sizes 10,50,100,200
bazel run //tools/benchmark:plan_bench -- examples/examples/itf/targets/*.itf.yaml --report plan-bench.md
```

Without Bazel, in an environment where ITF and its packs are installed or on `PYTHONPATH`:

```
python tools/benchmark/plan_bench.py test/integration/targets/localhost.itf.yaml --scale scopes
```

Paths are relative to the directory the command runs in (also under `bazel run`). A `policy.py` beside a target
file is loaded, as a run would load it.

| Option | Does |
|---|---|
| `TARGET_FILE...` | the target files to plan |
| `--scale KIND,...` | synthetic target files that grow along one axis (see below) |
| `--sizes N,...` | the sizes for `--scale` (default `10,50,100`) |
| `--reps N` | warm repetitions per target file (default 15); the median is reported |
| `--no-cold` | skip the fresh-process measurement (faster) |
| `--env NAME=VALUE` | a value for a `${NAME}` the target file uses (repeatable) |
| `--artifacts none\|standard\|full` | what the plans write to their run directory (default `none`); `full` measures the cost of every run file |
| `--report FILE` | write the full report as Markdown to `FILE`; the terminal shows the summary table and the file's link |
| `--check` | exit 1 when a threshold is exceeded or a target file does not plan (for CI) |

## Output

Without `--report`, the whole report goes to standard output as plain-text tables. With `--report FILE`, the
report goes to the file as Markdown, and the terminal shows the summary and a link:

```
target                                        roles  steps  warm ms  cold s  max gate ms  peak MiB  thresholds  note
--------------------------------------------  -----  -----  -------  ------  -----------  --------  ----------  ----
test/integration/targets/localhost.itf.yaml       4      1     4.80    0.23         0.19      0.27  ok
test/integration/targets/docker_ssh/docker_ssh.itf.yaml      7      2     6.16    0.21         0.26      0.28  ok
chain-50                                          1     50     9.65    0.20         2.39      1.23  ok

report: file:///home/user/itf/plan-bench.md
```

Progress lines (`planning ... `) go to standard error, so redirecting standard output captures only the report.

The report has these sections:

| Section | Shows |
|---|---|
| Environment | Python, machine, system, repetitions, artifact level |
| Summary | per target file: roles, steps, warm plan, fresh-process plan, the slower OCTO gate, peak memory, thresholds |
| Warm plan by phase | the median milliseconds of each planning phase, per target file |
| Median share of a warm plan | which phase costs what, across all target files |
| Fresh process | importing the core, the whole plan's wall time and the process's peak memory |
| Thresholds | the limits, and every value above one |

## What is measured

| Measure | How |
|---|---|
| warm ms | the median of `--reps` plans in one process, after a first plan imported everything |
| phases | each step of `Session.resolve()`, and OCTO's two gates inside it |
| cold s | one fresh Python process planning the target file once, imports included: what one `itf validate` or one Bazel compile step pays |
| peak MiB | the memory Python allocates during one more warm plan (`tracemalloc`) |
| peak RSS MiB | the fresh process's peak resident memory |

The phases:

| Phase | What it does |
|---|---|
| load | read the YAML, merge includes and override files, expand `${NAME}` |
| declare | load the packs the labels name and the policy, publish their parts |
| compile | turn the target file into claims for OCTO |
| octo_gate1 | OCTO decides what must exist: which factory fills each role, and the wiring |
| octo_gate2 | OCTO decides what must happen: which actions run, in which order |
| dry_run | resolve every implementation reference; construct nothing |
| artifacts | write the run directory, at the `--artifacts` level |

## Synthetic target files (`--scale`)

Each kind grows one axis, so a regression shows where it comes from:

| Kind | A target file of size n has |
|---|---|
| `scopes` | n devices of four `localhost` roles each, and a goal per device |
| `chain` | one role and n actions, each after the previous one |
| `deep` | n factories, each needing the one before |
| `wide` | n independent roles and n goals |

## Thresholds

`--check` fails above these. They are about 4 to 100 times what ITF's own target files measure on a 2016 laptop,
so they catch pathological target files and regressions, not machine noise:

| Measure | Warn above |
|---|---|
| a fresh process plans one target file | 2 s |
| a running process plans one target file | 250 ms |
| one OCTO gate | 100 ms |
| memory allocated while planning | 50 MiB |

## Reference numbers

The [2026-11-10 native QEMU report](native-qemu-2026-11-10.md) measures the current policy-aware
target composition plus scopes/chain/deep/wide sizes 10, 50 and 100. All 15 cases pass the existing
thresholds. On that development host, the observable QNX target has 12 roles and six steps, a warm
median of 8.82 ms, a cold plan of 0.34 s and 0.57 MiB peak traced memory. These are measurements of
that environment, not a before/after regression comparison or a guest-boot benchmark.

Grouped preflight was measured separately on the localhost target with one API family, two exact
Protocol profiles (one compatible and one incompatible), artifacts disabled and logging disabled.
After one warm-up, five repetitions of `Session.select` produced these medians:

| Collected tests | Selected / incompatible | Preflight median |
|---|---|---|
| 10 | 5 / 5 | 0.510 ms |
| 100 | 50 / 50 | 2.314 ms |
| 1000 | 500 / 500 | 18.931 ms |

The shape check is reused for identical profiles; per-test decisions and grouping still scale with
the collected suite. This separate measurement is not part of `plan_bench --check` thresholds.

On an Intel i7-6600U (2016, 2 cores), Python 3.12, for ITF's own target files:

| Measure | Value |
|---|---|
| warm plan | 3.5–7 ms |
| fresh process | 0.18–0.33 s (QEMU is the slowest: its configuration model loads pydantic) |
| both OCTO gates | under 1 ms |
| peak memory of a plan | under 0.5 MiB |
| a 200-device synthetic target (800 roles) | about 60 ms warm |
