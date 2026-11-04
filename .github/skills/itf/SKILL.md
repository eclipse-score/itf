---
name: itf
description: 'Compose and test targets with ITF (score_itf): write a target file (`*.itf.yaml`: roles, capability factories, goals, actions, relations, overrides), pytest tests that require roles, `itf_target` and `py_itf_test(target = ...)` in Bazel, and the project''s own parts (`@capability`, `@state`). Use when: asked what ITF can do on a target; writing or reviewing a target file, override file, policy, BUILD itf_target/py_itf_test or ITF test; "which factory gives X"; migrating a legacy ITF test (target.execute, docker_plugin); writing a pack; defining, mapping or enforcing a contract (`itf contracts map|new|check`); choosing a starter; validating, graphing, bringing up or tearing down a target (`itf validate|plan|graph|up|down|test`).'
argument-hint: 'A requirement, a role or factory label, a state, a contract name, or "how do I ..."'
---

# ITF: compose a target from self-describing parts, test by role

ITF is a platform to compose test targets from parts that describe themselves. OCTO plans from those
descriptions, and only those, before anything exists. Nothing is trusted on its name. Use these words and no
others; the full glossary is `docs/concepts/model.md#the-vocabulary`:

| Word | What it is | Example |
|---|---|---|
| target file | the `*.itf.yaml` document: roles, settings, goals (the Bazel rule is `itf_target`) | `target.itf.yaml` |
| target | what ITF builds for tests to use (the system under test and the means to reach it); described by a target file, used as `target.<role>` | `target.command` |
| part | a capability factory or an action | `docker.exec`, `ssh.open` |
| capability factory | `@capability("exec.command")`; label `<pack>.<function>` | `docker.exec`, `ssh.shell` |
| action | `@state("platform.up", ...)` with `@<action>.probe` | `docker.start` |
| capability contract, state contract | a name for what a test uses, a name for a condition | `exec.command`, `platform.up` |
| goal | a state listed under `goals:` | `platform.up` |
| role | a key of `capabilities:`; `target.<role>` | `command` |
| slot | a parameter of a part: what it needs | `platform: Platform` |
| scope | one device of a multi-device target | `gw` |
| override file | a target file holding only what changes | `override.itf.yaml` |
| policy | Python modules explicitly listed in YAML `policies:`: the project's ITF code (`itf_verify`, `itf_teardown`, parts labelled `local.<name>`); fixtures stay in `conftest.py` | `local.start_dlt_daemon` |

A part in the policy is `local.<name>`; `local` is reserved, no pack may use it. A pack is a directory with
`pack.yaml` and its parts. The pack for the test host itself is `localhost`.

**ITF knows no contracts.** A contract is whatever name two parts agree on. Definitions are optional. ITF
provides the contract map (`itf contracts map`), skeletons (`itf contracts new <name> --from-usage`) and
enforcement (`itf contracts check --rules`). The ITF team's contracts are a supported set, not a standard.

**Everything is explicit, nothing is required.** Goals are listed, not inferred; no part enters a target unless
listed; an empty target file is valid.

**Contract rule:** nothing imports a pack. Consumers write their *own* Protocols (a class with
`__contract__ = "<contract>"` and only the members they use); the planner checks at each seam that the
offering shape covers them.

## 0. Start from a starter

`examples/examples/starter/{container,ssh,serial}`: each has, in `targets/`, `target.itf.yaml` (with `# CHANGE:`
marks), `override.itf.yaml` and a policy (`itf_verify`, `itf_teardown`); beside it one test and a `BUILD` with `itf_target`
and `py_itf_test(target = ...)` (Bazel targets `:target`, `:test`, `:test_override`). Copy the closest,
change the marks and update `policies:` to the copied module's path. Run shipped examples from the `examples/`
MODULE root: their policy paths start with `examples/starter/...`, not relative to the YAML directory.
Other examples: `exec_everywhere` (one test file, four target files), `itf` (docker, dlt,
qemu), `vendor_contract` (a vendor's own contract), `plain_python`, `facade` (adopting ITF with a project's own target API). Tests written for the original API run unchanged on the compatibility layer (`score/itf/compat`).

## 1. The lifecycle

Which command answers which question, and the rules for using them: `references/cli.md`.

| Command | Does | Hardware |
|---|---|---|
| `itf validate [target] [--override f]` | every metadata rule | no |
| `itf plan` | the plan, readable; `--json`, `--output f` | no |
| `itf graph` | roles, wiring and bring-up sequence, Mermaid | no |
| `itf up [--detach]` / `itf down` | bring up and verify / unwind from observed state | yes |
| `itf test [target] [--override f] [-- pytest args]` | run the tests against the target file | yes |
| `itf doctor` | host prerequisites of the packs | reads |
| `itf diff old.json new.json` / `itf evidence <run-dir>` | compare plans / the summary page of a run | no |
| `itf contracts map [target...] [--format text\|json\|mermaid\|html] [--output f]` | discover | no |
| `itf contracts new <name> --from-usage [target...]` | writes `contracts/<name>.yaml` itself (no redirect) | no |
| `itf contracts reference --output f` | the Markdown reference of the defined contracts | no |

Under Bazel `itf` is `bazel run @score_itf//score/itf/cli:itf --`; policy paths resolve from caller working
directory via `BUILD_WORKING_DIRECTORY`, not the YAML parent. `bazel build //pkg:<name>` compiles a target file and writes `<name>.plan.json`: a wrong
target file fails the build with rendered diagnostics. Prefer `validate`, `plan` and `graph` to explore; use `up`
only when the user asks for a live target, never on real hardware to "check".

A run's directory (`itf-run/`) holds what a person reads by default (`test.log`, `target.html`, the evidence).
To look inside ITF itself, rerun with `--itf-artifacts=full` (or `--artifacts full`); `none` writes nothing.

## 2. Write a target file

```yaml
capabilities:
  platform:
    factory: docker.platform
    with:
      image: ubuntu:24.04
  command: docker.exec          # short form: just the factory
goals:
  - platform.up
```

Wiring comes from what the parts need: a slot with one candidate is bound to it; a factory's slot with several
needs `bind:` on its role; an action's slot with several needs `actions:` with `bind:`; a state two actions could
make true needs `by:` on the goal. The compiler names the line to write. A pack states no ordering that depends
on another pack, so orderings between packs are the target file's `relations:`:

```yaml
relations:
  - state: shell.open
    after:
      - platform.up
```

Details and every key (`include`, `packs`, `policies`, `capabilities`, `actions`, `goals`, `relations`, `assume`, `scopes`):
`references/yaml.md`. Swapping is changing one label: `command: docker.exec` becomes `command: ssh.exec`; the
test does not change.

Which target file a run uses is configuration, never policy code: `--itf-target`, `ITF_TARGET`,
`itf_target` in `pytest.ini`, `[tool.itf] target`, or `py_itf_test(target = ...)` (overrides:
`--itf-override`, `ITF_OVERRIDE`, `itf_override`, `[tool.itf] override`, `itf_target(overrides = [...])`).

## 3. Write tests

```python
from typing import Protocol
import score.itf as itf

class Command(Protocol):
    __contract__ = "exec.command"

    def exec(self, command: str) -> tuple[int, bytes]: ...

@itf.requires("command", shape=Command)
def test_hello(target):
    assert target.command.exec("echo -n hi") == (0, b"hi")
```

`@itf.requires(role, shape=YourProtocol, scope=...)` infers the contract from `__contract__` and checks
call structure, including positional and keyword arguments, not type assignability, return values or semantics.
Member-name lists (`shape=["exec"]`) remain backward compatible but do not check call structure.
Collection preflight groups exact consumer profiles by scope, role, contract and required major without
merging different signatures. Loose gating deselects incompatible or unknown tests; `--itf-strict-gating`
rejects collection before bring-up for applicable incompatible or unknown APIs. Missing roles/scopes and
explicit contract/major differences remain not applicable and deselected. Missing provider-major metadata
is unknown for a versioned requirement. `--itf-plan` prints preflight; full artifacts include `preflight.json`.

Policy baselines use `itf_expect = [YourProtocol]`: every capability offering that contract, in every scope,
is checked during resolution, even if no test consumes it. Missing contracts create no roles or requirements.
An unversioned baseline covers all majors; `name@1` covers explicitly offered major 1 and rejects matching
providers without major metadata. Multiple baselines compose; violations reject resolution even in loose mode.
Capability-provider majors are checked by preflight and policy. State `@major` is instead part of the exact
full runtime token: no stripping or implicit latest; reports retain the state major.

Use only members the consumer declares. Change state with
`session.reach("shell.open")`; `session.discard("platform")` dismantles a role and what is bound to it and reaches
nothing; `session.renew("platform")` is `discard` plus reaching the goals again. Readiness and evidence are
policy hooks (`itf_verify(session)` with `session.check(name, ok)`, `itf_teardown(session)`). Details:
`references/authoring.md`.

A requirement may also sit on a class (`@itf.requires` on it), a module or a package (`itf_requires =
itf.requires(...)`, or a list, at module level or in `__init__.py`); a test needs all of them.

## 4. Project parts, contracts, packs

- A part written in the policy is `local.<function>`. A project action is considered whenever its slots
  can be filled: if it makes a state true that a pack's action also makes true, target files need `by:`.
- Define a contract only when it adds something: `itf contracts new <name> --from-usage`, then fill the
  (rules: `namespaces`, `roles`, `forbid_stability`). Example: `examples/examples/vendor_contract`.
- A pack is a directory with `pack.yaml` (`name`, `version`, `prerequisites`), `providers.py` (the
  `@capability` factories), `steps.py` (the `@state` actions), `plugin.py`; loaded from labels
  (`score.itf.packs.<name>.plugin`, the entry point `score_itf.packs`, or the target file's `packs:` key). Each
  pack README has its label table. See `docs/how-to/plugins.md`.

## 5. Bazel

YAML explicitly selects the Python modules, for example when invoked from the project root:

```yaml
# ecu.itf.yaml
policies:
  - policies/common.py
  - policies/ubuntu.py
```

```starlark
load("@score_itf//:defs.bzl", "itf_target", "py_itf_test")

itf_target(name = "ecu", src = "ecu.itf.yaml", packs = ["@score_itf//score/itf/packs/docker"], srcs = ["policies/common.py", "policies/ubuntu.py"])
py_itf_test(name = "smoke", srcs = ["test_smoke.py"], target = ":ecu")
```

Paths are absolute or relative to invocation working directory: `./policy.py` works when invoked where
that file lives; `/home/alice/bench/policy.py` is an absolute example. No native directory discovery or
implicit `found.policy`: direct `Session`, CLI and pytest load the same YAML selection; legacy handling
stays in compat. Includes/overrides add policies deterministically and deduplicate paths; omission adds no
own policies and retains inherited ones, while explicit `policies: []` clears the inherited list. Duplicate
part labels across distinct modules remain errors. Contributions do not trigger actions absent goals.

`itf_target(name, src, overrides, packs, srcs, data, contracts, env, files, tools)`: `packs` are the packs the
factory labels may name (another pack fails the build), `srcs` bundle Python files selected by YAML (the test
does not list them). Any filenames and multiple modules are allowed, without a proximity restriction;
`srcs` does not select policies and there is no planner `--policy` selection. `files` carries the target-built
files the target file names as `${NAME}` (`{"ITF_IMAGE_LOAD": "//images:load"}`)
and `env` its other `${NAME}` values. `tools` has the same mapping but builds for the execution platform:
put tcpdump there, and leave QNX images in `files`. Tests inherit both: never add
`data`/`$(location)` for them. Container tests need `DOCKER_HOST` passed with `--test_env`.

## 6. Without pytest, and legacy

`from score.itf import Session; s = Session(target="x.itf.yaml", overrides=[...]); s.resolve();
s.bring_up(); s.target.command...; s.close()` (`resolve()` is a pure plan). Tests on the original API
run unchanged on the compatibility layer; `itf compat report` lists what is left to migrate (`docs/how-to/migrate.md`).
A project's own target API stays as an `itf.Facade` over the roles, served by overriding `target` in conftest.py
(`examples/examples/facade`, a tutorial); it needs no compatibility layer. What goes where: `docs/concepts/manifesto.md`.

## Checklist before answering

1. Roles named as the project's convention; labels `<pack>.<name>` that exist (read the pack README).
2. `itf validate` (or the `itf_target` build) passes; read `itf graph` for the order.
3. Tests ask for roles, not machines; no pack imports; YAML in block style.
4. New contract names: run `itf contracts map`; no disagreements.
