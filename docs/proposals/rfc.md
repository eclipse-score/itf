---
orphan: true
---

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

# RFC: compose ITF test targets from parts, and keep every existing test running

| | |
|---|---|
| **Status** | Proposed, open for review |
| **Reference implementation** | [`ihsa_itf_platform_bc`](https://github.com/ihebs3ideni/itf/tree/e12eda1ab65414932de090b87bf93365a99ec763), provided for evaluation; its commit boundaries do not prescribe how maintainers should integrate the proposal. |
| **Reading** | the [manifesto](https://github.com/ihebs3ideni/itf/blob/e12eda1ab65414932de090b87bf93365a99ec763/docs/concepts/manifesto.md) (principles, ownership and workflow), the [decision record](https://github.com/ihebs3ideni/itf/blob/e12eda1ab65414932de090b87bf93365a99ec763/docs/decisions/DR-002-arch-target-composition.md), the [migration guide](https://github.com/ihebs3ideni/itf/blob/e12eda1ab65414932de090b87bf93365a99ec763/docs/how-to/migrate.md) |

## Summary

Today a test target is a Python class, `Target`, with one subclass and one pytest plugin per environment (Docker,
QEMU); command-line options set it up and the bring-up order lives in each plugin. This RFC proposes that ITF
**composes** the target instead:

- A **target file** (`*.itf.yaml`) lists what a target is made of, by role (`command`, `files`, `shell`, ...),
  its explicit `policies:` and the states that must hold once it is up (`platform.up`, `shell.open`).
- **Packs** contribute the parts: a capability factory builds a thing tests use (`docker.exec`); an action makes
  a state true and comes with a probe that checks it, without changing anything.
- A small planner, **OCTO**, checks the parts against each other and orders the bring-up **before anything
  starts**. A target file that does not fit fails the build (`itf_target`), not the test run.
- Tests ask for roles and consumer APIs (`@itf.requires("command", shape=Command)`) and use them (`target.command`). The same test runs on the
  host, a container, a machine over SSH or a QEMU guest; what a target cannot offer is deselected with the reason.

**The original API remains available.** The original plugins, options, fixtures, imports and Bazel labels are
served by a compatibility layer over the same engine. A source-hash gate keeps ITF's legacy test bodies from
`main` byte-identical; integration BUILD wiring has been adapted to run those tests on the new implementation.

## Why

1. A new device means a new `Target` subclass with fixed methods; a device with other means forks the class.
2. Bring-up order is code inside each plugin; adding "flash, then wait for the network, then start DLT" means
   editing a plugin or ordering fixtures.
3. Tests are written per environment, and nothing tells the runner before the run that a test cannot run here.
4. Mistakes (a typo in an option, an image without SSH) appear after a machine started, often as a timeout.
5. A target is not data: it cannot be validated, drawn, diffed between branches, or brought up from a terminal.

## Three ways to run tests on the new ITF

| You have | You do | Shown by |
|---|---|---|
| tests on ITF's current API | keep the original plugins, options, fixtures and imports; the compatibility layer serves them | `test/integration/legacy`: byte-identical test bodies, with compatibility BUILD wiring |
| tests on your own target API | write target files, and keep your class as an `itf.Facade` over their roles | `examples/examples/facade`, a step-by-step tutorial |
| new tests | use the new API: `itf_target`, `py_itf_test(target = ...)`, `@itf.requires`, `target.<role>` | `test/integration`: the same ground as `legacy/`, rewritten |

The compatibility layer lives in one package (`score/itf/compat`); the original module paths only re-export
from it and from the packs, and a test enforces that. It switches on through the entry points a project already
uses, not through a setting, and says so once per run. `itf compat report` lists what a suite still uses of the
original API; `itf compat target` writes the target file its options make. The facade mechanism is part of the
core, so it stays when the layer is removed.

## What a project gets

- **Plans as build artifacts.** `bazel build //...` compiles every target file through both checks; `itf plan`,
  `itf graph` and `itf diff` show what will run and what a change does to bring-up, with no hardware.
- **One suite, many targets.** Gating decides per target which tests run, from the roles each target file offers.
- **Explicit policy composition.** A target's `policies:` selects its project-owned actions, expectations and
  hooks. No native filename or parent-directory discovery occurs. Policy paths are absolute or relative to
  the invocation working directory; includes compose lists and `[]` clears inherited selections. Bazel
  `srcs` bundles those files, but does not choose which modules load. Goals still choose which actions run.
- **Consumer-owned APIs.** Tests declare the Protocol they need. Providers may offer extra members and optional
  parameters; they must accept the calls the consumer declares. Grouped preflight checks requirements before
  bring-up; strict mode rejects incompatible or unknown applicable APIs, while loose mode deselects them.
  Module-level `itf_requires` declares the shared minimum; function requirements add only test-specific APIs.
  Callable checks validate argument structure, not return types or implementation semantics.
- **Policy-wide guarantees.** A policy's `itf_expect` validates every matching capability in every session scope,
  even if no test uses it, without creating or requiring absent roles. Violations fail resolution.
- **Versioned contracts and states.** Capability majors guide compatibility; state tokens such as `ready@1`
  and `ready@2` stay distinct throughout planning and execution. `itf versions` inventories and checks both.
- **Consistent contract metadata.** All 11 built-in packs have individual `contracts/<contract-id>.yaml`
  references to 21 canonical specifications in the shared contract library. References resolve from their
  declaring file, not the invocation directory. Shared specifications load once; independently authored
  definitions with the same name remain visible to duplicate-definition checks.
- **Observed state.** Every state has a probe; what already holds is kept, teardown undoes only what was done.
- **Secrets stay out of files.** `${NAME}` from the environment or a `.env` file, masked in logs and reports.
- **Evidence.** Each run leaves its plan, what the probes saw and a report (`itf evidence`).
- **Coverage across APIs.** `bazel coverage //...` measures `score/itf` across unit, integration and legacy
  tests; no new full-coverage percentage is claimed by this update.

## Possible integration strategy

This proposal adds only this Markdown document: no implementation or RST navigation changes. Maintainers
choose whether to adopt the design, how to divide the implementation for review, and its landing order.
The reference implementation is evidence for that discussion, not a prescribed set of pull requests.

One possible approach is to review related concerns in manageable groups:

- Build prerequisites and reproducible dependencies.
- Composition, policies, packs and compatibility as a coordinated change that preserves the original API.
- Contract metadata, CLI tooling, examples and documentation, grouped or staged as maintainers prefer.
- Conformance as an end-to-end capability, with its library, checks, YAML declarations, runners and tests
  reviewed together rather than split into incomplete pieces.
- Existing-infrastructure repairs separately where that makes review and reuse easier.

These are suggested review boundaries, not required commits, PRs or a fixed sequence. Maintainers may combine
or split them, request a smaller pilot, or choose another migration strategy. Any chosen sequence should keep
the supported API working and validate each intermediate state intended for release.

## How it was verified

Checks ran on combined implementation snapshots on 2026-11-10, not independently on every intermediate commit:

- The modernized shared suite passed on localhost, Docker, Docker/SSH and serial, together with contracts and
  shipped-target planning. Both QNX observability selections ran all 13 tests, through SSH and serial commands;
  managed QEMU renewal also passed. QNX used TCG, not KVM. That snapshot still included multicast DLT, which
  has since been removed; the reduced QNX selections have not been rerun.
- After the canonical-contract migration, six Bazel gates passed: contracts, generated catalog consistency,
  import-light behavior, CLI, shipped plans and core ITF. The exact CI `versions check --rules
  tools/contract_rules.yaml --tests test` command passed, including aliased Protocol inventory.
- All 21 canonical specifications retained their original semantic fields. A copied, installation-style package
  resolved all references. There is no wheel build configuration in this repository; no built-wheel pass is claimed.
- AST comparison preserved 60 existing suite/example test signatures, bodies and assertions. Three simulated
  vendor-contract tests and 17 example target/override plans passed. Legacy layer, shim and source-hash gates
  also passed during the migration.
- Conformance passed contracts and localhost, serial and Docker conformance under Bazel. The `observe.capture`
  and `observe.logs` checks in that run came from the multicast-era DLT module and have since been removed;
  those two contracts currently define no conformance checks.
  An isolated vendor run passed seven tests with built-in metadata visible but no built-in provider modules
  installed. The exact vendor Bazel target was blocked before analysis by an external registry timeout;
  that target is not claimed as a local Bazel pass.
- Generic contract, CLI and catalog functionality also passed 102 checks without the optional conformance
  implementation or YAML conformance metadata present.
- Earlier planning benchmarks passed all 15 thresholds. Grouped preflight medians were 0.510/2.314/18.931 ms
  for 10/100/1,000 tests; those numbers measure planning/preflight, not guest boot.
- A later [PR #154 workflow run](https://github.com/eclipse-score/itf/actions/runs/43014825445) passed
  `itf-build` (`bazel build //...`) and `itf-qemu-linux`. The Linux QEMU targets use Ubuntu and EB corbos Linux
  guests with QEMU, SSH and ping; they do not include the pcap/DLT observability packs. The workflow enables
  `/dev/kvm`, but QEMU tries KVM and then TCG, and the job summary does not establish which accelerator ran.
- The same run's `itf-test` job executed `bazel coverage --test_output=errors //...` and produced an aggregate
  LCOV artifact, but failed five Bazel targets. After fixes for those failures, focused local checks passed the
  affected targets and DLT pack tests; a green full-suite coverage run is still outstanding.
- After separating host packet capture, the common Docker observability suite passed locally without tcpdump,
  and the pcap-only Docker suite passed both capture tests after granting `CAP_NET_RAW` to the exec-configuration
  tcpdump binary. The pcap target is manual/local and has not run in ordinary CI. ITF's duplicate run-directory
  text log was removed; pytest/Bazel `test.log` retains the session header and output, while run evidence and the
  full-mode structured event stream remain available.

Known limits: Docker pcap observability is verified locally with `CAP_NET_RAW`, but the manual/local pcap target
has not run in CI. Linux-image QEMU integration passed, but Linux-image QEMU observability did not run, and the
selected QEMU accelerator was not confirmed. The QNX observability selections have not been rerun since multicast
DLT was removed. The aggregate coverage report was generated from a failing test
run; no green full-suite coverage result is claimed. `bazel build //...` passed and includes the `//:docs` target.

To close these limits: if Docker pcap coverage is required in CI, run the manual/local pcap target on a runner
that grants the host capture process `CAP_NET_RAW`; add and run a Linux-image QEMU observability target,
recording or enforcing KVM rather than silently accepting a TCG fallback; and rerun
`bazel coverage --test_output=errors //...` and require every target to pass; rerun both QNX observability
selections (SSH and serial) as part of the manual licensed-QNX gate.

The integration tutorial uses the existing QNX platform/configuration to select QEMU, and Docker otherwise;
serial has a fixed entry point sharing the same files, with no observability-specific flag or new platform.
The same tests consume `docker.exec`, `ssh.exec` or `serial.exec`; direct console tests remain separate and
are gated only on console APIs. No console tests were removed to obtain transport portability.
The tutorial uses Bazel `select()` to run the same tests against interchangeable target files;
target-specific tests have a fixed target, not a specialist marker. The QNX recipe covers serial, pcap
evidence, policy hooks, ordering and teardown. Licensed QNX execution is an explicit manual
pre-merge gate, not a claim that ordinary CI has an SDK and license.

## Costs and risks

| Cost or risk | Answer |
|---|---|
| A large change | maintainers can choose grouped or staged reviews, a smaller pilot, or another integration strategy; most lines are packs, tests and docs |
| Two APIs during migration | one engine; the old API is a thin layer in one package, measured by `itf compat report`, removable in one change |
| Small behaviour differences on the old API | listed in the migration guide (for example, QEMU's `target.execute` now includes stderr, as Docker's always did) |
| New concepts to learn | one glossary; the manifesto says what goes where; starters and a facade tutorial to copy |

## Open decisions

1. How long the compatibility layer is supported after it is deprecated: two minor releases, or a date?
2. After removal, is the layer published as a separate package for projects that still need it?
