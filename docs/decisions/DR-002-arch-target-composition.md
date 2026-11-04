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

# DR-002-Arch: Target Composition

**Date:** 2026-11-03
**Status:** Proposed

> This record follows the Decision Record convention established by the
> Eclipse S-CORE project:
> [eclipse-score/score — docs/design_decisions](https://github.com/eclipse-score/score/tree/main/docs/design_decisions).

## Context

ITF models a test target as one class, `Target`, subclassed per environment and created by one pytest plugin per
environment. Bring-up order lives in each plugin, tests call fixed methods, and every mistake shows up at run
time.

The design rests on four principles: a planner (OCTO) that plans from declarations only, parts that meet only
through names, probes as evidence, and teardown from observed state. This record decides how a target is described
and how parts declare themselves. The words are defined in the glossary of [the model](../concepts/model.md#the-vocabulary).

## Decisions

0. **Vocabulary.** A **target** is what ITF builds for tests to use: the system under test with everything
   needed to reach it. A **target file** (`*.itf.yaml`) describes it, the Bazel rule `itf_target` compiles it,
   and tests use it as `target.<role>`. ITF *composes* a target from parts: "composition" names the mechanism,
   never a file or a rule. A
   **part** is a capability factory or an action. Contracts are of two kinds: **capability contracts**, fulfilled
   by **capability factories** (`@capability`), and **state contracts**, fulfilled by **actions** (`@state`, with
   probes). A target file lists capabilities by role and states as goals.
1. **ITF knows no contracts.** A contract is whatever name two parts agree on, with whatever shape they publish
   and expect. ITF lets projects discover (`itf contracts map`), define (optional definition files,
   `itf contracts new --from-usage`) and enforce (`itf contracts check --rules`) their contracts. It does not
   ship a vocabulary everyone must follow. The ITF team maintains the contracts its own packs use, with
2. **A target file is keyed by role.** `capabilities:` maps a role to a factory label (`command: docker.exec`) or
   to a mapping with `factory`, `with`, `bind` or `remove: true`. A role is the stable key for duplicates (two
   consoles on one board), overrides, includes, scopes and tests (`target.debug`). Docker Compose does the same.
3. **Everything is explicit, and nothing is required.** Goals are listed, not inferred (`state`, plus `by` when
   two actions could make one state true). No part enters a target unless the target file lists it. An empty
   target file is valid. A slot with one candidate is bound to it; a slot with several says which with `bind:`
   (factories) or `actions:` (actions). Nothing is derived.
4. **Actions are bound like factories.** An action fills each slot with the role that `actions:` names, else the
   one role of the slot's contract in the scope, else it cannot run there. It is a candidate for a state only if
   all its slots can be filled.
5. **A target file states the orderings between packs.** An action carries only the `after` and `breaks` of the
   states it itself depends on. A pack does not know which other pack a project combines it with, so no pack
   hard-wires an ordering on another pack's state. The target file's `relations:` add those orderings. A relation
   on a state that no listed action makes true, and that is not assumed, is a compile error.
6. **The command line is the lifecycle:** `itf validate`, `plan`, `graph`, `up [--detach]`, `down` and `test`,
   plus `doctor`, `diff`, `evidence` and `itf contracts map|new|check|reference`. Nothing before `up` touches
   hardware. `down` unwinds from observed state, never by replaying the plan.
7. **Parts declare themselves in code.** `@capability("exec.command")` wraps a factory, and
   `@state("platform.up", after=..., breaks=...)` wraps an action with `@<action>.probe`. A slot is a parameter
   whose annotation, the consumer's own Protocol, carries `__contract__`. `config: <dataclass>` is the settings
   schema. The label is `<pack>.<function>`; the project's own parts are `local.<function>` (decision 14).
   Shapes check call structure, not type assignability or semantics. Capability-provider majors are checked
   by preflight and policy. State `@major` is part of the exact full runtime token, never stripped or resolved
   to an implicit latest; reports retain the state major.
8. **Override files** are target files that hold only what changes, merged by role. `remove: true` takes a role
   out. A different factory in the same role starts from no settings.
9. **Tests ask for roles:** `@itf.requires("<role>", shape=YourProtocol)` and `target.<role>`; the consumer
   owns the Protocol with its `__contract__`. Older member-name lists remain supported without call-structure checks. A
   requirement can also sit on a test class, a module or a package (`itf_requires = itf.requires(...)`); a test
   needs every requirement on it and above it. Collection preflight groups exact consumer profiles by scope,
   role, contract and required major without merging different signatures. Loose gating deselects incompatible
   or unknown tests; `--itf-strict-gating` rejects collection for applicable incompatible or unknown APIs.
   Missing roles/scopes and explicit contract/major differences remain not applicable and deselected;
   missing provider-major metadata is unknown for a pinned major.
10. **One session, one discovery.** `Session(target=..., overrides=...)` is the one session of every front.
    `resolve()` plans and builds nothing. `bring_up()` runs the actions. `reach`, `discard`, `renew` and `probe`
    change and read state during tests, always through the planner. The target file is found in the same order
    by pytest, the command line and Bazel: explicit value, `ITF_TARGET`, `pytest.ini`, `pyproject.toml`.
11. **Packs load from labels.** `docker.exec` loads the pack `docker`, from ITF, from an installed entry point,
    or from the target file's `packs:` key.
12. **Bazel:** `itf_target` compiles the target file during the build, so a target file that does not
    compile fails `bazel build`. `py_itf_test(target = ...)` runs tests against it. The target file reaches
    the test as written; no document is generated. `itf_target` supplies the target file's `${NAME}` values
    (`files` for built files, `env` for the rest).
13. **Existing tests keep running.** The compatibility layer, `score/itf/compat`, serves the original plugins,
    fixtures, options, imports and Bazel labels over the packs, whose classes carry the original names.
14. **The project's policy.** A project's own ITF code (`itf_verify`, `itf_teardown`, its own capability
   factories and actions) is its **policy**: Python modules explicitly listed in YAML `policies:`, not
   discovered from directories. Paths are absolute or relative to invocation working directory, not the
   YAML parent (`BUILD_WORKING_DIRECTORY` under `bazel run`). Direct Session, CLI and pytest share this
   selection. Conftests stay pytest's, for fixtures. The policy's parts are labelled `local.<name>`, and `local`
    is reserved: no pack may be named `local`, so `local.x` always means this project's policy. The policy
    outranks the target file, which outranks the packs. The pack for the test host is `localhost`. A project's
    rules over contracts are **contract rules** (`itf contracts check --rules rules.yaml`).
   API baselines use `itf_expect = [YourProtocol]`: all matching capabilities in every scope are checked during
   resolution, even without test consumers; missing contracts are not required. Baseline violations reject
   resolution independently of strict/loose test gating.

## No trust

Nothing is accepted because a name matches. Each rule comes from the party that cares about it:

| Rule | Checked against | When |
|---|---|---|
| a slot's expected shape | the shape the offering factory publishes | target file |
| an action's `after`, `breaks`, `also` | every other action's claims and the target file's relations | target file |
| a part's settings schema | the target file and override values | target file |
| a pack's host prerequisites | the host (`itf doctor`) | before bring-up |
| a test's requirement | the composed target | collection |
| an action's claim to have made a state true | its own probe | after it runs, before reuse, at teardown |

## Alternatives

| Option | Rejected because |
|---|---|
| Keep `Target`, add capability mixins | Keeps fixed methods and per-plugin ordering; checks stay at run time |
| A target file keyed by part label, or a list of parts | No stable name when a part is used twice, and none for overrides and tests |
| Derive missing parts when one fits | Hidden parts in a plan; explicit lists are easier to review |
| A fixed contract vocabulary with a registry and namespaces | ITF cannot know every project's devices; a registry needs governance nobody asked for |
| Names owned by contracts (`target.<member>`) and packs with variants | Turned target file into filling fixed slots and lost OCTO's idea of building from parts |
| Starlark recipes compiled to a document read by hooks | A second format, and target files must work without Bazel |
| Naming the file and rule after the mechanism (`composition.itf.yaml`, `itf_composition`), or after a place (`testbed`, `environment`) | The first names how ITF works, not what a test gets; the second adds a word next to `target`, which tests already use |
| Orderings declared by packs (`ssh.open` after `platform.up`) | Wrong for a machine that is already running; the target file knows, the pack does not |

## Consequences

- A project that wants its own contracts needs no registration or release. It names them, maps them, and adds
- Every target file states the orderings between the packs it combines. The starters show the common ones.
- Two actions that could make one state true, or a slot with two candidates, are errors at target file time.
  The error names both and the line to write.
- The original plugins and `Target` are served by the compatibility layer (`score/itf/compat`), so existing tests
  run unchanged and migrate one at a time.
- A different kind of target is a different target file; `include:` shares the common part.
