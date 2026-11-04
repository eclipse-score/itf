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

# The ITF platform: lifecycle, fronts and packs

The words are defined in the glossary of [the model](model.md#the-vocabulary). One engine, many fronts:

```text
                 parts (packs)          contracts (definitions, optional)
                        \                    /
                         target file
                                 |
                       OCTO plan (validated, drawable)
                 /          |            |            \
          itf CLI     pytest adapter   facade      plain Python
```

## The lifecycle

Every command that works on a target file takes it (an argument, or the configured one) and `--override` files.
Nothing before `up` touches hardware.

| Command | Does | Touches hardware |
|---|---|---|
| `itf validate` | every metadata rule: wiring, shapes, majors, settings, action order | no |
| `itf plan` | the plan, readable; `--json` for tools | no |
| `itf graph` | the topology (roles and wiring) and the bring-up sequence, as Mermaid | no |
| `itf doctor` | host prerequisites of the target file's packs | reads the host |
| `itf up` | bring up, verify, print the target; `--detach` leaves it running | yes |
| `itf down` | unwind from what the probes observe | yes |
| `itf test [target] [--override F] [-- pytest args]` | run the tests against the target file (pytest underneath); what follows `--` is pytest's | yes |
| `itf diff old.json new.json` | compare two `plan.json` files; exit 1 if they differ | no |
| `itf evidence <run-dir>` | write `evidence.html` for a run (`--summary` aggregates several) | no |
| `itf contracts map`, `new`, `check`, `reference` | discover, scaffold, enforce and document the project's contracts | no |

`itf down` after `itf up --detach` needs no state file: ITF unwinds from observed state, never by replaying the
plan, so a part that can observe what it created (a container found by its labels) can be torn down by a later
process. A part that cannot observe says so, and `--detach` is refused for it.

With Bazel, `itf` is `bazel run @score_itf//score/itf/cli:itf --`. Policy modules are explicitly selected by
YAML `policies:`; their paths are absolute or relative to the invocation working directory, not the YAML
parent. Under `bazel run`, `BUILD_WORKING_DIRECTORY` supplies the caller's working directory.

## Plans are build artifacts

`itf_target(name = "ecu", src = "ecu.itf.yaml")` compiles the target file during the build, exactly as a test
run does (both gates, nothing constructed), writes `ecu.plan.json`, and fails the build with ITF's
diagnostics when the target file does not compile or when a factory label names a pack that is not in `packs`.
`py_itf_test(target = ":ecu")` runs tests against it; its pack dependencies are the `packs` listed there, and
its policies are selected by YAML and bundled by the rule's `srcs`, so the test does not list them.
For the snippet below, `ecu.itf.yaml` must explicitly declare `policies: [./policy.py]`; invoke from the
project root containing that Python file. `srcs` does not select policies or require a particular filename.

```starlark
itf_target(
    name = "ecu",
    src = "ecu.itf.yaml",
    overrides = ["lab2.itf.yaml"],
    packs = ["@score_itf//score/itf/packs/docker", "@score_itf//score/itf/packs/ssh"],
    srcs = ["policy.py"],
)

py_itf_test(name = "smoke", srcs = ["test_smoke.py"], target = ":ecu")
```

The plan has three keys: `target` (roles, the factory chosen for each, redacted settings), `action` (ordered
steps, each naming the action that runs it) and `assumptions`. It is deterministic, so two plans compare as text.

## Which target file a run uses

Said once, in configuration, never in the policy, and found by one discovery that the pytest adapter, the `itf`
command line and Bazel share: `--itf-target` (and `--itf-override`, repeatable), then the environment
(`ITF_TARGET` and `ITF_OVERRIDE`), then the `itf_target` and `itf_override` ini options in `pytest.ini`,
then `[tool.itf]` with `target` and `override` in `pyproject.toml`; Bazel sets them from
`py_itf_test(target = ...)`. Several override files are separated by `os.pathsep`. The policy holds code
only: `itf_verify(session)`, `itf_teardown(session)`, and the project's own factories and actions. Fixtures
stay in `conftest.py`.
See [the model](model.md#which-target file-a-run-uses).

## The pytest adapter

`pytest` builds the target from the target file, gates each test on its requirements, gives tests the `target`
fixture, and unwinds at the end. Packs load from the factory labels (`docker.exec` loads `docker`); a label
whose pack cannot be found fails with the packs it knows. `itf test` is the same, started from the command
line. `--itf-plan` prints the plan and the gating and runs nothing; `--itf-fresh` runs every planned action
ignoring what probes observe; `--itf-keep` skips unwind. Collection preflight groups exact consumer profiles by
scope, role, contract and required major without merging different signatures. Loose gating deselects
incompatible or unknown tests; `--itf-strict-gating` rejects collection before bring-up for applicable
incompatible or unknown APIs. Missing roles/scopes and explicit contract/major differences remain not applicable
and deselected; missing provider-major metadata is unknown for a pinned major. Protocol checks cover call
structure, not type assignability or semantics; older member-name lists remain supported without these checks.
Policy `itf_expect = [YourProtocol]` checks every matching capability in every scope during resolution, even
without test consumers; it does not require missing contracts. Violations reject resolution in either mode.
Capability-provider majors are checked by preflight and policy. State `@major` remains part of the exact full
runtime token, with no stripping or implicit latest; reports retain the state major.
`--itf-bring-up-attempts N` (default 1) lets bring-up plan again when an action fails and a state that held
before, or that an earlier action delivered, no longer holds: a guest that panics while booting stops its
machine, so the boot is planned and run again, up to N attempts. A failure that loses no state is not retried,
since planning again from the same observation would run the same failing action. `evidence.html` lists
every attempt, with the states each retried one lost, and marks its failed step `failed, retried`, which does
not fail the run; `target.html` draws the last attempt and names the retries in its summary.

Tests change state through the planner: `session.reach("shell.open")` re-establishes what an action invalidated;
`session.discard("platform")` dismantles a role and everything bound to it and reaches nothing, so the next
access builds them afresh; `session.renew("platform")` is `discard` followed by reaching the goals again.
Per-test isolation is a fixture you own that calls `renew`; pytest's scopes decide when, the planner what.

## Existing tests: the compatibility layer

Tests written for the original API (the docker, qemu, dlt and core dump plugins, `Target`) run unchanged. The
compatibility layer, `score/itf/compat`, translates the original options into a target file, starts the session
on it, and serves the original fixtures and `Target` methods over the composed roles. The packs' classes carry
the original names (`Ssh`, `Sftp`, `DltReceive`, `ping`), and the original module paths and Bazel labels only
re-export them. The mechanism under it is ITF's core and open to projects: an `itf.Facade` keeps a project's own
target API over the roles of its target file, without the compatibility layer. See [Migrate](../how-to/migrate.md).

## Plain Python

`Session(target="ecu.itf.yaml", overrides=[...])` is the same session without a test runner: `resolve()`
makes the plan and builds nothing, `bring_up()` runs the actions, `session.target` is the target, `close()`
unwinds. `score.itf.Session` is the core `Session`. See `examples/examples/plain_python`.

## Packs

A **pack** is a directory with a `pack.yaml` (`name`, `version`, `prerequisites`) holding parts: capability
factories and actions. Core reads one thing from `pack.yaml`: the name. Packs load from a label, `<pack>.<name>`, as the
module `score.itf.packs.<pack>.plugin` or, for a pack outside the ITF repository, the entry point
`score_itf.packs:<pack>`. Packs never import each other; they meet only through contract names. A pack states no ordering that depends
on another pack: an action's `after=` names only states the action itself needs, and a target file adds the rest
with `relations:`. For a pack outside the ITF repository that is not installed, the target file's `packs:` key
names its module (`acme: acme.plugin`).

| Pack | Offers (labels) |
|---|---|
| `local` | `localhost.platform`, `localhost.exec`, `localhost.process`, `localhost.files`, action `localhost.start` |
| `docker` | `docker.platform`, `.exec`, `.process`, `.files`, `.endpoint`, action `docker.start` |
| `ssh` | `ssh.shell`, `.exec`, `.process`, `.files`, action `ssh.open` |
| `serial` | `serial.console`, `.pty_console`, `.exec`, action `serial.open` |
| `net` | `net.endpoint`, `.key`, `.password` |
| `qemu` | `qemu.platform`, `.endpoint`, `.credentials`, `.console`, actions `qemu.start`, `.open_console` |
| `ping` | `ping.pinger`, action `ping.await_boot` |
| `dlt` | `dlt.receive`, `.receive_tcp`, `.on_target`, action `dlt.start_receive` |
| `pcap` | `pcap.capture`, actions `pcap.start`, `.start_on_host` |
| `core_dump` | core-dump extraction at teardown |
| `sim` | in-memory stand-ins for offline runs |

Each pack's README carries its label table, host prerequisites and a target file excerpt.

## Evidence

Run artifacts go to `$TEST_UNDECLARED_OUTPUTS_DIR/itf-run` (else `itf-run/`). How much a run leaves there is
one setting: `--itf-artifacts` (pytest), `--artifacts` (`itf`), `ITF_ARTIFACTS`, or `itf_artifacts` in `pytest.ini`.

| Level | The run directory gets |
|---|---|
| `none` | no run directory: ITF's output is what pytest prints (Bazel's `test.log`) and what tests write themselves |
| `standard` (default) | what a person reads: after a bring-up, `target.html` (the plan and what ran) and `evidence.html` with `evidence.json`; when planning fails, `diagnostics.txt` (and `target.html` when there is a plan to draw). A plan that compiles writes nothing |
| `full` | every file ITF writes, for debugging ITF or a pack: also `plan.json`, `claims.json`, `gating.json`, `preflight.json`, `run.json`, `unwind.json`, and `events.jsonl` |

Pytest owns the text log (`test.log` under Bazel); ITF does not write a duplicate text log in its run directory.
`--itf-log-level` changes the structured event stream's level in full mode. A failure report names the run directory only when there
is one. `itf plan --json` and `--output` print or write the plan without a run directory. A policy's
`itf_teardown` saves what a person needs to follow the run (console transcript, container output) while the target
still runs.
