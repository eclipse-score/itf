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
# Integration Test Framework (ITF)

ITF is a platform to **compose test targets from self-describing parts**, for testing ECUs and the software on
them, with [`pytest`](https://docs.pytest.org) and Bazel. A target file says what a target is made of;
**OCTO** (Open Contract Topology Orchestration) plans it from the parts' own metadata, before anything exists;
your tests ask for what they need. Write a test once and run it in a Docker container, on a QEMU virtual machine or
on real hardware: moving it is changing one word in the target file, not the test.

Nothing is trusted on its name. Every part brings its rules (what it needs, what it offers, what it makes true,
how to check it), and the parties that depend on a claim check it.

## Start here

1. Read [Start here](docs/how-to/start_here.md): three questions (where does your software run, how does ITF reach
   it, what do your tests need) lead you to a starter.
2. Copy a starter from [`examples/examples/starter`](examples/examples/starter): `container`, `ssh` or `serial`.
   Each has a target file with `# CHANGE:` marks, an override file, a policy and a test.
3. Follow the [tutorial](docs/how-to/tutorial.md): copy a starter, validate, graph, bring it up, test, swap a
   factory, override a value for one setup.

```
itf validate target.itf.yaml                  # every metadata rule, no hardware
itf graph target.itf.yaml                     # roles, wiring and the bring-up sequence
itf up --detach target.itf.yaml               # bring it up and leave it running
itf down target.itf.yaml                      # unwind from what the probes observe
itf test target.itf.yaml -- -k hello          # bring up, run the tests, tear down; after `--`, pytest's own arguments
```

## A target file, a test

```yaml
# target.itf.yaml
capabilities:
  platform:
    factory: docker.platform
    with:
      image: ubuntu:24.04
  command: docker.exec
goals:
  - platform.up
```

```python
# test_hello.py
from typing import Protocol

import score.itf as itf

class Command(Protocol):
  __contract__ = "exec.command"

  def exec(self, command: str) -> tuple[int, bytes]: ...

@itf.requires("command", shape=Command)
def test_hello(target):
  assert target.command.exec("echo -n hello") == (0, b"hello")
```

```starlark
# BUILD
load("@score_itf//:defs.bzl", "itf_target", "py_itf_test")

itf_target(name = "target", src = "target.itf.yaml", packs = ["@score_itf//score/itf/packs/docker"])
py_itf_test(name = "test_hello", srcs = ["test_hello.py"], target = ":target")
```

`bazel build :target` compiles the target file and writes its plan (a wrong target file fails the build,
before any image is built); `bazel test :test_hello` runs the test. If the target file has no `command`, the test
is deselected with the reason. **Swapping is changing one word:** `command: docker.exec` becomes
`command: ssh.exec` and the test does not change.

## The vocabulary

The full glossary is in [the model](docs/concepts/model.md); these are the words, and no others.

| Word | What it is | Example |
|---|---|---|
| **target file** | the `*.itf.yaml` document: roles, settings, goals and selected policies | `target.itf.yaml` |
| **target** | the composed thing at run time (`target.<role>`), never the file | `target.command` |
| **part** | a capability factory or an action | `docker.exec`, `docker.start` |
| **capability factory** | a part that builds what a test uses: `@capability("exec.command")` | `docker.exec` |
| **action** | a part that makes a state true, with a probe: `@state("platform.up")` | `docker.start` |
| **capability contract**, **state contract** | the names parts agree on: what a test uses, a condition | `exec.command`, `platform.up` |
| **goal** | a state listed under `goals:` | `platform.up` |
| **role** | a key under `capabilities:` | `command` in `target.command` |
| **slot** | a parameter of a part: what it needs | `platform: Platform` |
| **label** | `<pack>.<name>`, or `local.<name>` | `ssh.shell` |
| **pack** | a directory with `pack.yaml` and its parts | `docker` |
| **policy** | an explicitly selected Python file contributing checks, evidence and project-owned parts | `policies/common.py` |
| **override file** | a target file holding only what changes | `override.itf.yaml` |

## Where each thing is defined

| Thing | Defined in |
|---|---|
| a part's label, contract, slots, shape, settings, probes | the pack's code: decorators, slots, annotations, dataclasses |
| what a target is made of, its goals, its orderings and its policies | its target file |
| project-owned parts, readiness checks and evidence | Python files explicitly listed in `policies:` |
| what differs in one setup | its override file |
| what a test needs | `@itf.requires("<role>", shape=ConsumerProtocol)` |
| which target file a run uses | configuration: `--itf-target`, `ITF_TARGET`, `itf_target` in `pytest.ini`, `[tool.itf] target`, or Bazel `py_itf_test(target = ...)` |

## No trust

| Rule | Brought by | Checked against | When |
|---|---|---|---|
| "I need a shell with `run` and `exec`" | the part that needs it | the shape the offering part publishes | target file |
| "I make `shell.open` true; I need `platform.up`; I break `network.reachable`" | the action, and the target file's `relations:` | every other action's claims | target file |
| "My settings are `port: int`" | the part's config schema | the target file and override values | target file |
| "I need tcpdump on PATH" | the pack | the host (`itf doctor`) | before bring-up |
| "I need a `command` with `exec`" | the test | the composed target | collection (gating) |
| "I did make `shell.open` true" | the action | its own probe | bring-up, every run |

## Contracts are your project's own

ITF knows no contracts: a contract is whatever name two parts agree on. ITF lets a project **discover** them
(`itf contracts map`: who offers and who needs each name, with which shape, and every disagreement), **define**
--from-usage` writes a skeleton file) and **enforce** its rules (`itf contracts check --rules rules.yaml
[target...]`, exit 1 on violations). The ITF team maintains the contracts its own packs use, with
[Use, define and enforce contracts](docs/how-to/contracts.md) and
[`examples/examples/vendor_contract`](examples/examples/vendor_contract).

## The lifecycle

| Command | Does | Touches hardware |
|---|---|---|
| `itf validate` | every metadata rule | no |
| `itf plan` | the plan, readable; `--json` for tools | no |
| `itf graph` | roles, wiring and the bring-up sequence, as Mermaid | no |
| `itf doctor` | host prerequisites of the target file's packs | reads the host |
| `itf up [--detach]` | bring up, verify, print the target | yes |
| `itf down` | unwind from what the probes observe | yes |
| `itf test [target] [--override F] [-- pytest args]` | run the tests against the target file | yes |
| `itf diff old.json new.json` | compare two plans | no |
| `itf evidence <run-dir>` | the summary page of a run | no |
| `itf contracts map`, `new`, `check`, `reference` | discover, scaffold, enforce and document contracts | no |

Every command that takes a target file takes it as an argument, or reads the configured one; `--override` adds
override files. With Bazel, `itf` is `bazel run @score_itf//score/itf/cli:itf --`.

## pytest, existing tests, plain Python

- **pytest:** the target file comes from configuration, never from code. The project's ITF code is its
  explicitly selected policies: `itf_expect`, `itf_verify`, `itf_teardown` and its own parts (`local.<name>`).
  No policy is discovered by filename or directory. pytest fixtures stay in `conftest.py`.
- **Existing tests** written for the original API run unchanged: the compatibility layer (`score/itf/compat`)
  serves the original plugins, fixtures, options and Bazel labels over the packs; see
  [Migrate](docs/how-to/migrate.md).
- **A project's own target API** stays as it is: an `itf.Facade` writes its methods over the
  target file's roles, so its tests keep their shape and only the infrastructure changes; the tutorial is
  [examples/examples/facade](examples/examples/facade/README.md).
- **Plain Python** composes and runs a target without a test runner:
  `Session(target="target.itf.yaml")`; see `examples/examples/plain_python`.

Select policies in the target file:

```yaml
policies:
  - ./policies/common.py
  - ./policies/ubuntu.py
```

Paths are relative to the invocation working directory, not the YAML directory; absolute paths also work.
With no declarations, no policies load. Includes and overrides compose policy lists in order, deduplicating
files; `policies: []` clears inherited selections. Listing a policy contributes its parts and checks, but goals
still decide which actions must run. A policy's `itf_expect` declares API expectations before bring-up; runtime
verification and teardown belong in hooks.

## Bazel

`itf_target(name, src, overrides, packs, srcs, data, contracts, env, files, tools)` validates the target file during
the build and writes `<name>.plan.json`. It supplies `${NAME}` values through `files` for target-built assets,
`tools` for execution-platform tools and `env` for other values. Its `srcs` bundle the selected policy files
and their Python helpers; the YAML's `policies:` list alone selects what loads, with no filename or proximity
restriction. `py_itf_test(target = ":name")` inherits those files and values. For the policies above, list
`srcs = ["policies/common.py", "policies/ubuntu.py"]` on `itf_target`, not on the test. See the
[Bazel macros](docs/reference/bazel_macros.rst).

## Packs

| Pack | Labels |
|---|---|
| `docker` | `docker.platform`, `.exec`, `.process`, `.files`, `.endpoint`; action `docker.start` |
| `qemu` | `qemu.platform`, `.console`, `.endpoint`, `.credentials`; actions `qemu.start`, `.open_console` |
| `ssh` | `ssh.shell`, `.exec`, `.process`, `.files` (SFTP); action `ssh.open` |
| `net` | `net.endpoint`, `net.key`, `net.password` |
| `ping` | `ping.pinger`; action `ping.await_boot` |
| `dlt` | `dlt.multicast`, `dlt.receive`, `dlt.receive_tcp`; actions `dlt.join`, `.start_receive` |
| `pcap` | `pcap.capture`; actions `pcap.start`, `.start_on_host` |
| `serial` | `serial.console`, `serial.pty_console`, `serial.exec`; action `serial.open` |
| `local` | the test host: `localhost.platform`, `.exec`, `.process`, `.files`; action `localhost.start` |
| `core_dump` | core files copied off the target at teardown |
| `sim` | in-memory stand-ins for offline runs |

A pack states no ordering between its actions and another pack's: a target file says it with `relations:`. Each
pack's README has its label table, host prerequisites and a target file excerpt.

## Guides

- [Start here](docs/how-to/start_here.md), [tutorial](docs/how-to/tutorial.md) and
  [get started](docs/how-to/get_started.md).
- [Write tests](docs/how-to/write_tests.md): target files, overrides, scopes, gating, `reach`, `discard` and `renew`.
- [The manifesto](docs/concepts/manifesto.md): the principles, capabilities and states, probes, gating, and who
  owns what. Read it before writing a pack, a target file or a test.
- [The model](docs/concepts/model.md) and [the platform](docs/concepts/platform.md).
- [Contracts](docs/how-to/contracts.md) and [why ITF composes targets](docs/decisions/DR-002-arch-target-composition.md).
- [Migrate](docs/how-to/migrate.md): from the original plugin API.
- [OCTO](score/itf/core/octo/README.md): the planner on its own.
- [Agent skill](.github/skills/itf/SKILL.md): a guide for coding agents.

## Original API

Tests written for the original plugins and `Target` class run unchanged on the compatibility layer: the original
imports, fixtures, options and Bazel labels are served by the new engine and the packs, whose classes carry the
original names (`Ssh`, `Sftp`, `DltReceive`, ...). ITF's original tests run unchanged against it (`test/integration/legacy`).
`itf compat report` lists what a suite still uses, and `itf compat target` writes the target file its options
make (see [Migrate](docs/how-to/migrate.md)).

## Requirements

Bazel builds every dependency, including a hermetic C/C++ toolchain, DLT and tcpdump. Host prerequisites, checked
when used: a Docker-compatible daemon (Docker or Podman) for the docker pack, `qemu-system-*`, `qemu-img` and
`/dev/kvm` for the qemu pack, and `CAP_NET_RAW` for packet capture.

Tests reach the engine through `DOCKER_HOST`, which Bazel does not pass to tests on its own. With rootless Podman,
start the socket, name the variable, and run tests unsandboxed so that image loading can write to `/run`:

```bash
systemctl --user enable --now podman.socket
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
bazel test //examples/exec_everywhere/... \
  --test_env=DOCKER_HOST --test_env=XDG_RUNTIME_DIR --strategy=TestRunner=local   # from examples/
```

## Development

```bash
bazel test //...                      # unit, framework, pack, container and compatibility tests
bazel coverage //...                  # the same, with line coverage of score/itf (LCOV)
python3 tools/coverage_summary.py bazel-out/_coverage/_coverage_report.dat   # per-area summary
bazel run //:format.fix               # ruff + buildifier
bazel run //:copyright.check          # license headers
bazel run //:docs_check               # the docs, warnings as errors
bazel run //:requirements_3_12.update # after editing requirements.in
```

Checks that touch no hardware and start nothing, so they run anywhere. Under Bazel `itf` is
`bazel run //score/itf/cli:itf --`; paths are relative to where you run it. A target file whose `${NAME}` values
come from its `itf_target` needs them in the environment or a `.env` beside it. Every command is in
[score/itf/cli/README.md](score/itf/cli/README.md).

```bash
bazel build $(bazel query 'kind(_itf_target, //...) except attr(tags, manual, //...)')   # compile every target file, as CI does
itf validate test/integration/targets/localhost.itf.yaml   # one target file: exit 1 with diagnostics
itf plan test/integration/targets/localhost.itf.yaml       # which factory fills each role, actions in order
itf plan --json --output new.plan.json test/integration/targets/localhost.itf.yaml   # the plan as data
itf graph --kind both test/integration/targets/localhost.itf.yaml   # wiring and bring-up sequence, as Mermaid
itf diff old.plan.json new.plan.json  # what a change does to bring-up; exit 1 when they differ
itf doctor test/integration/targets/localhost.itf.yaml     # what the packs need on this host (tools, devices, engines)
itf contracts map                     # every contract in use: offerers, needers, tests, disagreements
itf contracts check --rules tools/contract_rules.yaml   # the project's contract rules, as CI does
itf contracts new <name> --from-usage # a definition skeleton from the shapes in use
itf contracts map --format html --output docs/_generated/catalog.html   # regenerate the checked-in pages
itf contracts reference --output docs/reference/contracts.md
itf compat report tests/ BUILD        # what a suite still uses of the original API
itf compat target --docker-image=ubuntu:24.04 --out /tmp/targets   # the target file the original options make
itf evidence itf-run/                 # a report of a finished run (itf evidence --summary run1/ run2/ compares)
```

`itf up`, `itf down` and `itf test` bring targets up; they need what the target file names.

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.
