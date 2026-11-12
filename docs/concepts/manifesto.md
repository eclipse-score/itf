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

# The ITF manifesto: what ITF is for, what goes where

ITF exists so that a test says **what it needs** and never **how to get it**. Everything in this page follows from
that sentence. It is written for everyone who touches ITF: people who write tests, people who bring a project's
machines to ITF, people who write packs, and the people who review all of them. The words are the ones in the
glossary of [the model](model.md#the-vocabulary); [Modeling a target](modeling.md) has the short rules for
writing parts.

## Principles

1. **Tests ask, targets answer.** A test names the roles it uses (`target.command`) and asserts what the product
   does. Which machine, how it starts and how it is reached are the target file's business.
2. **Compose, do not configure.** A target is made of parts that each do one thing. A new machine is a new
   combination of parts in a target file, not a new class or a new flag.
3. **Plan before anything runs.** What will be built and in which order is decided from the target file alone,
   before anything starts, and can be read, drawn and checked in a build (`itf_target`).
4. **Nothing implicit.** Goals are listed, never inferred. Parts are wired by contract names and slots, and where
   two could fit, the target file says which (`bind:`). Nothing enters a target unless a target file lists it.
5. **Observe before you act.** Every state has a probe. What already holds is kept, so a run starts from what is
   there, not from what a script assumed.
6. **No part is trusted on its name.** A part brings its shape, its settings schema and its checks; parts check
   each other through them. A contract is a name parts agree on, not shared code.
7. **One implementation.** A capability is written once, in one pack. Compatibility layers and facades wrap it;
   they do not copy it.
8. **Infrastructure stays out of tests.** Addresses, images, credentials and benches live in target files,
   override files and the environment. A test never names them.
9. **Secrets never sit in files.** A login is a `${NAME}` read from the environment or a `.env` file, marked
   sensitive, and masked in every log and report.
10. **Failures mean the product is wrong.** A test that cannot run where it is is deselected with the reason,
    not failed. A failure is reserved for the product.

## Capabilities and states

The first question for every fact is: **is it a thing a test uses, or a condition that holds?**

| | Capability | State |
|---|---|---|
| What it is | a thing a test uses: an object with members | a condition of the target that is true or false |
| Grammar | a noun: a command runner, a console, a log stream | a statement: the platform is up, the session is open |
| Declared by | a capability factory, `@capability("<contract>")` | an action, `@state("<state>")`, with a probe |
| In the target file | a role under `capabilities:` | a goal under `goals:`, ordered by `relations:` |
| In a test | `target.command.exec("uname -a")` | `target.reach("logs.active")`, or a goal reached before tests |
| Examples | `exec.command`, `files.transfer`, `observe.logs`, `logs.on_target` | `platform.up`, `shell.open`, `logs.active` |

Most things a test relies on come as a pair: the **object** is a capability, and **being ready** is a state. An
SSH session is the `shell` role (`exec.shell`, what tests call) and the state `shell.open` (whether it is
connected). Keep them apart: the factory builds the object without connecting; the action connects; the probe asks
whether it is connected.

A capability never starts anything when it is built. Building is cheap and side-effect free, so a plan can
build every role in any order and a dry run touches nothing. Starting, connecting, booting and subscribing are
actions, because only actions are ordered, observed and undone.

A condition that no action can make true (multicast routes between host and target, a bench has KVM) is not a
state ITF reaches. If it holds without ITF, the target file says so with `assume:` and an owner. If it decides
whether a test can run, it belongs to the target file that offers the roles, not to a check inside the test.

## Probes

A probe answers one question: **does this state hold right now?** It is what makes ITF safe to rerun: a state
whose probe says yes is not made true again, and teardown undoes only what was observed.

A probe:

- **changes nothing.** It reads; it never starts, restarts, writes, mounts, cleans or retries an action. A probe
  that changes the target makes every plan a lie.
- **measures the real thing.** It asks the target (the process answers, the port accepts, the daemon replies), not
  a flag the action set in Python. After a reboot only the real thing tells the truth.
- **is cheap and bounded.** It returns in about a second and has its own short timeout. Waiting until something
  holds is the action's job, never the probe's.
- **is specific.** It checks its own state only. A state that needs another first says so with `after=`; the
  probe does not check the other state too.
- **returns a boolean.** True means the state holds. An exception means ITF cannot tell, which counts as not
  holding and is logged; it is not a way to report "false".
- **is safe to call at any time:** before the action ran, in the middle of a run, after teardown.

An action and its probe are written together, so the action's postcondition is exactly what the probe checks:

```python
@state("shell.open", after=("platform.up",))
def open_shell(shell: Shell) -> None:
    shell.connect()                  # makes it true, waiting as long as it must

@open_shell.probe
def shell_is_open(shell: Shell) -> bool:
    return shell.is_connected()      # asks, changes nothing, returns quickly
```

## Capability factories (providers) and contracts

In the code a factory is a *provider*: it provides a contract. In ITF's words it is a **capability factory**,
and its label (`docker.exec`) is what a target file places in a role.

Design a factory so it fits any target, not only the one in front of you:

- **Name the contract after what a test does with it**, not after the technology: `exec.command`, not
  `docker.run`. Two packs that offer the same thing offer the same contract, so a test moves between them
  untouched.
- **Publish the object's shape by its return type.** Its public members are the contract's members; a member
  starting with `_` is not part of it.
- **Take what you need through slots**: parameters annotated with your own Protocol that sets `__contract__` and
  lists only the members you call. Never import another pack: you would depend on its code, not on its contract.
- **Settings are a frozen dataclass named `config`**, each field typed, secrets marked sensitive. A value that
  differs per setup is a setting, never a constant.
- **Construction starts nothing**, as above. Clean up in the factory (a generator that yields the object), so a
  role is torn down when it goes.
- **One factory, one job.** A factory that builds a container and opens a shell in it is two factories and an
  action.
- **State only your own ordering.** `after=` and `breaks=` name states your action itself depends on or undoes.
  An order that comes from how two packs are combined is the target file's `relations:`.

A contract may carry a major version (`exec.command@1`), a definition with members and guarantees, and
conformance checks that every factory offering it must pass. Adding members within a major never breaks a
consumer, because consumers list the members they use. A new major is a new contract for consumers that say so.

## Gating

A test declares what it needs with `@itf.requires("<role>", shape=YourProtocol, scope=...)`, on the test,
its class, its module or its package (`itf_requires`). Gating compares those needs with the plan **at
collection**, before anything starts:

- a test whose needs the target file meets runs;
- any other test is deselected with the reason ("the target file has no `logs` role"), so one suite runs on many
  targets and each runs what it can;
- grouped preflight keeps exact consumer profiles by scope, role, contract and required major, without merging
   different signatures. Loose gating deselects incompatible or unknown tests; `--itf-strict-gating` rejects
   collection for applicable incompatible or unknown APIs. Missing roles/scopes and explicit contract/major
   differences remain not applicable and deselected; missing provider-major metadata is unknown for a pinned major.

The consumer owns its Protocol, with `__contract__` and only the members it uses. Checks cover call structure,
not type assignability or semantics; older member-name lists remain supported without call-structure checks.
Policy `itf_expect = [YourProtocol]` checks every matching capability in every scope during resolution, even
when no test consumes it, but does not require missing contracts. Baseline violations reject resolution in
both gating modes. Capability-provider majors are checked by preflight and policy; state `@major` is part of
the exact full runtime token, never stripped or resolved to an implicit latest, and retained in reports.

Gating is about what the target **offers**. It is not:

- a way to pick tests by environment name (`if bench == "lab3"`); select tests with the runner's own selection;
- a runtime check inside the test (`if not target.has("logs"): pytest.skip()`): say it with `@itf.requires`, so
  the decision is visible before the run and in the plan;
- a substitute for an assertion: a role that exists but misbehaves is a failure.

## Who owns what

Every fact has one owner. When a change lands in the wrong place, the design starts to rot: a test that knows an
IP address, a pack that knows another pack, a runner flag that changes bring-up.

| Owner | Owns | Never owns |
|---|---|---|
| **Runner** (pytest, Bazel, the `itf` command line, CI) | collecting and selecting tests by name or marker, running them, parallelism, reports, retries of whole tests, where outputs go | how a target is built, the order of bring-up, which machine a test uses |
| **ITF core** | the plan (both gates), bring-up and teardown in order, probes and reuse, gating, `reach`/`discard`/`renew`, evidence, masking secrets, the target file format | any technology (no docker, ssh, dlt in the core), any project's values |
| **Packs** | parts for one technology: factories, actions with probes, their settings, the contracts they offer with definitions and conformance checks | other packs' code, orderings between packs, project values, test logic |
| **Project** (the integrators) | target files and override files per machine, the policy (`policy.py`: readiness checks in `itf_verify`, evidence in `itf_teardown`, project-specific parts `local.<name>`), facades over its own target API, contract rules | product assertions, technology code that should be a pack |
| **Testers** | tests: the roles they need (`@itf.requires`), what they do with them, what the product must do; pytest fixtures for test data in `conftest.py` | bring-up, addresses, credentials, waiting for boot, cleanup of the machine, choosing a target |
| **Infrastructure** (labs, CI, IT) | machines, images, networks, benches, credentials and their storage, the environment variables and `.env` files a target file reads | anything inside the test or the target file's structure |

Two boundaries cause most confusion:

- **Policy or pack?** Code that every project with this technology would need is a pack. Code that only makes
  sense for this project (its own daemon, its LED check) is a policy part, labelled `local.<name>`.
- **Policy or conftest?** ITF code (hooks, parts) goes in the policy, which ITF loads. Pytest fixtures go in
  `conftest.py`, which pytest loads. ITF refuses its code in a conftest and says where it belongs.

## The workflow

Every step works on the target file before anything starts, and each step has one tool. The `itf` command line
works without Bazel; under Bazel it is `bazel run //score/itf/cli:itf -- <command>`, and `itf_target` runs the
same checks in the build.

### Bringing a machine to ITF (project)

1. **Start from a starter** (`examples/examples/starter/<container|ssh|serial>`): a target file with `# CHANGE:`
   marks, an override file, a policy and one test.
2. **Check the host:** `itf doctor targets/<name>/<name>.itf.yaml` reports what the packs need on this machine
   (tools, devices, a container engine).
3. **Check the target file:** `itf validate ...` compiles it through both gates and exits 1 with what is wrong
   and how to fix it. Nothing starts.
4. **Read the plan:** `itf plan ...` prints which factory fills each role and which actions run in which order;
   `itf graph ...` draws the wiring and the bring-up sequence. If the plan is not what you meant, change the
   target file, not the tests.
5. **Try it by hand:** `itf up ...` brings the target up and opens a Python console on it (`target.command...`);
   leaving the console takes it down. `itf up --detach` leaves it running and `itf down` takes it down later, for
   factories that can observe what exists.
6. **Put it in the build:** an `itf_target` per machine. From then on a target file that stops compiling fails
   the build, and its plan is a build output (`<name>.plan.json`).
7. **Per bench:** an override file holds the facts of one setup; logins come from the environment or a `.env`
   file, never from the target file.

### Writing tests (testers)

1. Write the test against roles, with `@itf.requires("<role>")` on the test, its class, module or package.
2. Run it: `bazel test //path:<test>`, or `itf test targets/<name>/<name>.itf.yaml -- -k <name>` without Bazel.
3. Read the log: each deselected test says which need the target file did not meet. A deselection is not a
   failure; fix it in the target file if the test should run there.
4. Read the evidence: pytest owns the text log (`test.log` under Bazel); the run directory (`itf-run/`) holds
   the plan and what the probes observed. `itf evidence itf-run/` writes a report, `itf evidence --summary
   run1/ run2/` compares runs.

### Writing a pack (pack authors)

1. Write the parts: factories, actions with probes, settings dataclasses; slots with your own Protocols.
2. Define the contracts others will offer or need: `itf contracts new <name> --from-usage` writes a definition
   skeleton from the shapes in use; add guarantees and conformance checks.
3. See where you stand: `itf contracts map` lists every contract in use, who offers it, who needs it, which tests
   ask for it, and every disagreement.
4. Add a target file for the pack under `test/integration/targets/`, so the generic suite runs on it, and a
   conformance run.

### Reviewing and CI

1. Build every `itf_target`: a target file that does not compile fails before any machine is touched.
2. Compare plans between two versions: `itf diff old.plan.json new.plan.json` shows what a change does to
   bring-up.
3. Enforce the project's contract rules: `itf contracts check --rules rules.yaml [target files]`.
4. Run the tests; keep the run directories as evidence.

### Moving existing tests

`itf compat report tests/ BUILD` lists every use of ITF's original API with its replacement; `itf compat target
--docker-image=... --out targets/` writes the target file the original options make. Tests on a project's own API
move with a facade (`examples/examples/facade`).

## Facades and the compatibility layer

A project with tests on its own target API keeps them: its target class becomes an `itf.Facade` written over the
roles of a target file and is served as `target` from `conftest.py`. A facade translates an API; it does not
start, wait or decide. If a facade method needs a condition, that condition is a state of the target file; if it
needs a machine, that machine is a role. ITF's original API is served the same way by the compatibility layer, for
a deprecation period. Neither copies a capability; both wrap the packs' objects.

## Abuses, and what to do instead

| Abuse | Why it hurts | Instead |
|---|---|---|
| A test reads an IP address, image name or password | the test is tied to one bench, and secrets leak | a setting in the target file, `${NAME}` from the environment |
| A test or fixture starts, restarts or waits for the machine | bring-up is invisible to the plan and repeated per suite | an action with a probe, listed as a goal; `target.reach(...)` or `renew(...)` when a test needs it again |
| A factory connects or boots when built | dry runs and plans touch hardware; order is hidden | construction starts nothing; an action does it |
| A probe "fixes" what it finds (restarts a daemon) | reruns change the target; the plan lies | the probe reports; the action fixes |
| A probe sleeps until something holds | runs become slow and the plan cannot tell holding from waiting | the action waits; the probe asks once |
| A pack imports another pack | packs become one tangle; a second provider cannot replace the first | declare a slot with your own Protocol |
| A contract named after a technology (`docker.run`) | tests cannot move between technologies | name it after the use (`exec.command`) |
| A role per environment (`command_lab3`) | targets leak into tests | one role name; one target file per environment, or an override file |
| A runner flag that changes bring-up (`--use-qemu`) | the runner decides what the target is | a target file per machine; a `select()` of `itf_target`s by platform |
| `if not target.has(...)` skips inside tests | decisions hidden until runtime | `@itf.requires` on the test, class, module or package |
| A facade with logic (retries, waits, sequencing) | a second, untested framework grows inside the project | states and roles in the target file; the facade only translates |
| Copying a pack's class into a project to change it | two implementations drift | contribute the change to the pack, or write a new factory for the same contract |

## For reviewers

Before approving a change, ask:

1. Does every test name only roles, and assert only product behaviour?
2. Is every new condition a state with an action and a probe that changes nothing?
3. Does every new factory start nothing when built, take its needs through slots, and import no other pack?
4. Is the contract named after its use, and does it have a definition when others will offer it?
5. Is every value that differs per setup a setting, and every secret a `${NAME}` marked sensitive?
6. Is every ordering between packs in the target file, and every ordering inside a part in its `after=`/`breaks=`?
7. Does each piece of code sit with its owner in the table above?
