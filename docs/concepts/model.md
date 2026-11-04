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

# The ITF model: what things are called, where each fact lives, who decides

ITF is a platform to **compose test targets from self-describing parts**. A part says what it offers, what it
needs, what it makes true, what it breaks and how to check that it did its job. OCTO (Open Contract Topology
Orchestration) reads those descriptions, and only those, checks that every part's rules are met by the others,
and produces a plan before anything exists. The plan can be validated, drawn, brought up and torn down. Tests
are one consumer of the composed target; a person at a terminal is another; an old framework behind a facade is
a third.

The principles behind it, and who owns what, are in [the manifesto](manifesto.md).

Nothing is trusted on its name. Every claim is checked by the party that depends on it (see
[No trust](#no-trust-every-part-brings-its-rules-and-they-check-each-other)).

## The vocabulary

This is the one glossary. Every other page, the README and the agent skill use these words and no others; they
link here. A word that is not on the list is not ITF's.

| Word | What it is | Example |
|---|---|---|
| **target file** | the `*.itf.yaml` document that says what a target is made of: roles, settings, goals; with its includes and override files. The Bazel rule that compiles one is `itf_target` | `target.itf.yaml` |
| **target** | what ITF builds for tests to use: the system under test with everything needed to reach it, made of the roles a target file lists. Described by a target file, compiled by `itf_target`, used as `target.<role>` in a test and `session.target` in Python. ITF *composes* a target from parts | `target.command` |
| **part** | a capability factory or an action: one piece of code that a pack or a project contributes | `docker.exec`, `ssh.open` |
| **capability factory** (factory) | a part that builds a capability a test uses: `@capability("exec.command")` | `docker.exec`, `ssh.shell` |
| **action** | a part that makes a state true, with a probe that checks it: `@state("platform.up", ...)` | `docker.start`, `ssh.open` |
| **capability contract** | a contract fulfilled by a factory: something a test uses | `exec.command` |
| **state contract** | a contract fulfilled by an action: a condition that can be made true and checked | `platform.up`, `shell.open` |
| **state** | the name of a condition. `@state` is only the decorator that declares an action | `platform.up` |
| **goal** | a state listed under `goals:`: what must be true once the target is up. Goals are listed, never inferred | `platform.up` |
| **slot** | a parameter of a part: what the part needs, written as the part's own Protocol with a `__contract__` | `platform: Platform` |
| **role** | a key under `capabilities:`: the name a placed factory answers to, `target.<role>` | `command` |
| **label** | the name of a part: `<pack>.<name>`, or `local.<name>` for a part in the project's policy (`policy.py`) | `docker.exec`, `local.status_led` |
| **pack** | a directory with a `pack.yaml` and its parts | `docker`, `ssh`, `dlt` |
| **policy** | Python modules explicitly selected by the target file's `policies:` list: the project's own ITF code (`itf_verify`, `itf_teardown`, its own parts, labelled `local.<name>`). No native directory discovery; `local` is reserved for project parts | `local.start_dlt_daemon` |
| **contract rules** | a project's rules over contracts, enforced by `itf contracts check --rules rules.yaml` | `rules.yaml` |
| **scope** | one device of a multi-device target; the roles of a scope are `target.<scope>.<role>` | `gw` |
| **override file** | a target file that holds only what changes; merged by role over another target file | `override.itf.yaml` |
| **plan** | what OCTO resolves from a target file: which factory fills which role, and which actions run in which order | `itf plan` |
| **gate** | one of the two checks that produce the plan: gate 1 decides what must exist (factories, slots, shapes, settings), gate 2 decides what must happen (actions and their order, from the goals) | "plan failed at gate 2" |
| **probe** | the check that says whether a state holds right now; it never changes anything | `@open_session.probe` |
| **contract map** | the generated page, and `itf contracts map`, that lists every contract in use: who offers it, who needs it, which tests ask for it | `docs/_generated/catalog.html` |
| **ITF** | the product: this framework | |

Two more words appear in target files. An **assumption** (`assume:`) is a state that holds without ITF, with an
owner and a reason. A **relation** (`relations:`) is a statement about the order of states that a target file
adds to what the actions already say about themselves.

## A part, declared

```python
class Shell(Protocol):                  # the consumer's own Protocol, never shared code
    __contract__ = "exec.shell"         # which contract this shape describes

    def run(self, command: str) -> str: ...

@capability("exec.command")             # label: <pack>.exec, from the function name
def exec(shell: Shell) -> SshExec:      # the parameter is a slot: contract and shape from its annotation
    return SshExec(shell)

@state("shell.open")
def open_session(shell: Shell) -> None:
    shell.connect()

@open_session.probe
def session_open(shell: Shell) -> bool:
    return shell.connected()
```

- `@capability` wraps a capability factory, `@state` an action. `after=` and `breaks=` are an action's own
  state relations; `also=` lists further states one action makes true. A pack states no ordering that depends on
  other packs: a target file adds those with `relations:`.
- A **slot** is a parameter. Its annotation's `__contract__` names the contract; its members are the shape the
  part expects. No other parameter is allowed, except `config`.
- `config: <dataclass>` is the settings schema: what a target file gives under `with:`.
- The label is `<pack>.<function name>`, or `label=`. Capability contracts accept `@major`; pinned consumers
  require an explicitly offered matching major, checked by preflight and policy. State names use the exact
  full runtime token, including `@major`: no suffix stripping or implicit latest. Reports retain the state major.

## A target file

This is a whole target file, a container running sshd and a shell session into it
(`examples/examples/starter/ssh/targets/target.itf.yaml`). `itf validate` accepts it.

```yaml
capabilities:
  platform:
    factory: docker.platform      # <pack>.<name>
    with:                         # the factory's settings, checked against its schema
      image: linuxserver/openssh-server:version-10.2_p1-r0
      command: null
      init: false
      environment: PASSWORD_ACCESS=true,USER_NAME=score,USER_PASSWORD=score
      ports: 2222/tcp
  endpoint:
    factory: docker.endpoint
    with:
      port: 2222
  credentials:
    factory: net.password
    with:
      user: score
      password: score
  shell: ssh.shell                # short form: just the factory
  command: ssh.exec
goals:
  - platform.up
  - shell.open
relations:
  - state: shell.open             # the session connects to a service of the container
    after:
      - platform.up
```

The keys of a target file, in the order they are merged:

| Key | Says |
|---|---|
| `include` | target files merged first, in order; this file wins |
| `packs` | where a pack that is not installed lives: `acme: acme.plugin` (pack name to the module of its entry point) |
| `capabilities` | the roles. Each is a factory label, or a mapping with `factory`, `with` (settings), `bind` (slot to role, only when a slot has more than one candidate) or `remove: true` (take the role out, see override files) |
| `actions` | how an action's slots are filled, when a slot has more than one candidate: the action's label with `bind:` (slot to role) |
| `goals` | the states to reach: a state name, or `state:` with `by:` (an action label) when two actions could make it true |
| `relations` | order between states, added to what the actions say about themselves: `state:` with `after:` and/or `breaks:` (lists of states) |
| `assume` | states that hold without ITF: `state:` with an optional `owner:` and `reason:` |
| `scopes` | more devices, each with `capabilities`, `actions`, `goals`, `relations` and `share` |

`actions` and `relations` are also keys of a scope, and mean the same there with that scope's roles and states.
Unknown keys are errors that name the keys that exist.

**Everything is explicit, and nothing is required.** Goals are listed, not inferred. No part enters a target
unless the target file lists it. An empty target file is valid.

### How the wiring is decided

| Question | Answer, in this order |
|---|---|
| which role fills a factory's slot | `bind:` on the role; else the one role of the slot's contract in the scope; else an error naming the candidates |
| which role fills an action's slot | `actions:` with `bind:`; else the one role of the slot's contract in the scope; else the action cannot run there |
| which action makes a goal true | `by:` on the goal; else the one action that can run in the scope; else an error naming both |
| in which order | the actions' own `after`/`breaks`, plus the target file's `relations:` |

The actions considered are those of the packs of the listed factories plus the project's own. An action is a
candidate for a state in a scope only if all of its slots can be filled. A state that no listed action makes
true or that is not assumed, and that a relation names, is a compile error.

Two consoles on one board show `actions:`: `serial.open` has one slot, `console`, and two roles fit it.
`itf validate` says so and what to write:

```yaml
capabilities:
  console:
    factory: serial.pty_console
    with:
      shell: /bin/sh
  debug:
    factory: serial.pty_console
    with:
      shell: /bin/sh
  command:
    factory: serial.exec
    bind:                         # a factory's slot with two candidates
      console: console
goals:
  - console.open
actions:
  serial.open:                    # an action's slot with two candidates
    bind:
      console: console
```

Roles are keyed by name because a role is the stable key for everything else: duplicates (two consoles on one
board are two roles), overrides, includes, scopes and tests all use it. It is also what Docker Compose does.

### Order between states: `relations:`

An action says what it needs of the states it knows: its own `after=` and `breaks=`. A pack does not know which
other pack a project combines it with, so it states nothing about them. The target file does:

A fragment of a target file:

```yaml
relations:
  - state: shell.open
    after:
      - platform.up          # open the session only once the platform is up
    breaks:
      - network.reachable    # and opening it ends this state
```

These are added to the claim of the action that makes `shell.open` true.

### Several devices

```yaml
capabilities:
  platform: localhost.platform
  command: localhost.exec
scopes:
  gw:
    capabilities:
      command: localhost.exec
    share:
      - platform             # gw uses the root's platform role
```

Tests use `target.gw.command`. A scope never falls back to the root; what it uses of the root, it lists under
`share:`.

## Override files

An override file is a target file holding only what changes: for one setup (an image, a login, a retry count),
or for one kind of run. It is merged by role over the target file, after its includes, in the order given. This
one points the SSH target file above at a real machine (`itf validate targets/target.itf.yaml --override
targets/override.itf.yaml` accepts the pair):

```yaml
capabilities:
  platform:
    remove: true                  # no container here: the machine already runs
  endpoint:
    factory: net.endpoint         # a different factory fills this role
    with:
      host: 10.0.0.7
      port: 22
  credentials:
    with:
      user: lab                   # only this setting changes
assume:
  - state: platform.up
    owner: lab
    reason: the machine is powered and booted by the lab
```

`with:` and `bind:` keys are merged, any other key replaces, goals and assumptions merge by state, and `relations:`
of one state are joined. `remove: true` stands alone and takes a role out (and a role can be added back by a later
file). A factory that replaces another starts from nothing: the old settings do not carry over. `${NAME}` and
`${NAME:-default}` in a `with:` value read the environment, else a `.env` file beside the target file (`NAME=value`
lines; git should ignore it, so logins stay out of a shared target file; commit a `.env.example` instead), else the
default (a value that is exactly one reference is read as a
YAML scalar, so `port: ${SSH_PORT:-22}` is an integer; `$${` is a literal `${`).

**Secrets never show.** A settings field marked sensitive (`field(metadata={"sensitive": True})`), or every
setting of a `@capability(..., sensitive=True)` factory, is a secret. Its value is redacted in plans, claims and
reports, and while a session runs it is masked as `[redacted]` in every log record (pytest's live and captured
logs, and the structured `events.jsonl` stream in full artifact mode), in failure reports, in the evidence and in
pytest's failure output and JUnit report. Values
shorter than 6 characters are only redacted, not masked, since masking a short word would hide it in names too.

## Which target file a run uses

Said once, in configuration, never in the policy. The pytest adapter, the `itf` command line and Bazel all
read it the same way, first match wins:

| Source | Target file | Override files |
|---|---|---|
| the command line | `--itf-target` (pytest), the `target` argument (`itf`) | `--itf-override` (pytest, repeatable), `--override` (`itf`, repeatable) |
| the environment | `ITF_TARGET` | `ITF_OVERRIDE` |
| `pytest.ini` or `[tool.pytest.ini_options]` | `itf_target` | `itf_override` |
| `pyproject.toml` | `[tool.itf] target` | `[tool.itf] override` |
| Bazel | `py_itf_test(target = ":x")` | the `overrides` of the `itf_target` |

Several override files are separated by `os.pathsep` in the environment, the ini and `pyproject.toml`.
The target file explicitly lists policy modules in `policies:`; filenames and locations are unrestricted.
Paths are absolute or relative to the invocation working directory, not the YAML parent; under `bazel run`,
`BUILD_WORKING_DIRECTORY` supplies the caller's working directory. `./policy.py` works when invoked where
that file lives. Direct `Session`, CLI and pytest load the same selection, without implicit `found.policy`.
Includes and overrides add policies in deterministic order and deduplicate paths. An omitted key adds no
own policies and retains inherited ones; explicit `policies: []` clears the inherited list. Duplicate part
labels across distinct modules remain errors. Legacy discovery stays in compat.

Policies hold `itf_verify`, `itf_teardown` and project parts labelled `local.<name>`; pytest fixtures stay in
`conftest.py`. Contributions alone do not trigger actions absent goals. See
[Get started](../how-to/get_started.md#add-readiness-and-evidence-the-policy) for YAML and Bazel examples.

## Tests ask for roles

`@itf.requires("command")` means the target has a role `command`. A consumer-owned Protocol with
`__contract__ = "exec.command"` narrows it via `@itf.requires("command", shape=Command)`; the test then uses
`target.command`. Protocol checks cover call structure, not type assignability or semantics. Older member-name
lists (`shape=["exec"]`) remain supported but do not check call structure.
Collection preflight groups exact consumer profiles by scope, role, contract and required major, without merging
different signatures. Loose gating deselects incompatible or unknown tests; `--itf-strict-gating` rejects
collection for applicable incompatible or unknown APIs. Missing roles/scopes and explicit contract/major
differences remain not applicable and deselected; missing provider-major metadata is unknown for a pinned major.
Policy `itf_expect = [YourProtocol]` checks all matching capabilities in every scope during resolution, even
without test consumers. It does not require missing contracts; violations reject resolution in either mode.
Which role names a project uses is the project's convention; `itf contracts check` can enforce it (the role
`command` is always an `exec.command`).

## Changing state while tests run: `reach`, `discard`, `renew`

A session is the one run of a target file: `resolve()` makes the plan and nothing else, `bring_up()` runs the
actions, `session.target` is the target, `close()` unwinds. Tests change state only through the planner:

| Call | Does |
|---|---|
| `session.reach("shell.open")` | runs the actions needed to make the state true again (what an action invalidated) |
| `session.discard("platform")` | dismantles the role and every built role bound to it, and reaches nothing: the next access builds them afresh, so a caller can adjust the new object first. States whose evidence ran through them are forgotten until the next `reach` |
| `session.renew("platform")` | `discard` followed by a reach of every goal reached so far |
| `session.probe()` | runs the probes and returns the states that hold |

Per-test isolation is a fixture you own that calls `renew`: pytest's scopes decide when, the planner what.

## ITF knows no contracts

A contract is whatever name two parts agree on, with whatever shape they publish and expect. ITF does not ship a
vocabulary everyone must follow: it is the platform that lets a project discover, map, define and enforce its own.
Plans are the compiler: they tell you, from metadata, whether a target file would work. The ITF team

| Tool | Does |
|---|---|
| `itf contracts map [target...]` | every contract name in use, from the loaded parts and tests: who offers it (with which shape), who needs it (expecting which members), which tests ask for it, whether a definition exists, and every disagreement; `--format text\|json\|mermaid\|html`, `--output FILE` |
| `itf contracts new <name> --from-usage [target...]` | writes a definition skeleton, built from the shapes observed in the map, to `contracts/<name>.yaml` (or `--out FILE`); it never overwrites |
| `itf contracts reference --output FILE` | the Markdown reference of the defined contracts |

Without any definition a target file still compiles: wiring and gating use names, and the no-trust checks use the
See [Use, define and enforce contracts](../how-to/contracts.md) and the `vendor_contract` example.

## No trust: every part brings its rules, and they check each other

Nothing is accepted because a name matches. Each rule comes from the party that cares about it.

| Rule | Brought by | Checked against | When |
|---|---|---|---|
| "I need a shell with `run` and `exec`" | the part that needs it (its slot's annotation) | the shape the offering part publishes | target file, from metadata |
| "I fulfil `exec.command@1`" | the offering factory | the contract definition, when there is one (the offered major is no newer than the definition, every required member is offered) | target file |
| "I make `shell.open` true; I need `platform.up`; I break `network.reachable`" | the action, and the target file's `relations:` | every other action's claims; OCTO orders or refuses | target file |
| "My settings are `port: int`, `password` is secret" | the part's config schema | the target file and override values | target file |
| "I need tcpdump on PATH" | the pack | the host (`itf doctor`) | before bring-up |
| "I need a `command`, version 1, with `exec`" | the test (`@itf.requires`) | the composed target | collection (gating) |
| "I did make `shell.open` true" | the action | its own probe, run right after | bring-up |
| "It is still true" | the probe | the target, again, before reuse and at teardown | every run |

The engine's only job is to hold every party to its own word and to the words of its neighbours.

## Who decides what

| Question | Decided by |
|---|---|
| what a target is made of | the target file |
| which factory fills a role | the target file (`bind` and `by` only where a choice is real) |
| what must exist, and in which order | gate 1, from the parts' needs |
| what must happen, and in which order | gate 2, from the goals, the actions' `after` and `breaks`, and the target file's `relations:` |
| whether a state holds | its probe, never the plan |
| which tests run | gating, against the composed target |

## Where each fact lives

| Fact | Lives in | Only there |
|---|---|---|
| a part's label, contract, slots, shape, settings, probes | the pack's code: decorators, slots, annotations, dataclasses | yes |
| a pack's prerequisites and version | its `pack.yaml` | yes |
| what a target is made of, its goals, its orderings | its target file | yes |
| what differs in one setup | its override file | yes |
| what a test needs | `@itf.requires` | yes |
| which target file a run uses | configuration (see above) | yes |
| ITF code: readiness, evidence, project parts | the policy (`policy.py`) | yes |
| pytest fixtures | `conftest.py` | yes |

## What successful platforms got right, and what ITF takes

| Platform | What works | ITF |
|---|---|---|
| Terraform | declarative desired state; `validate`, `plan`, `apply`, `destroy`; variables files per environment; `graph`; drift shown by `plan` | a target file; `itf validate`, `plan`, `up`, `down`; override files per setup; `itf graph`; drift shown by probes |
| Docker Compose | one file says what runs; `up`, `down`; an override file per environment | one file says what the target is made of; `itf up`, `down`; an override file per setup |
| Bazel | labels say where a thing comes from; analysis before execution; typed information is carried between rules | part labels say which pack a part comes from; the plan before bring-up; contracts carry names and shapes between parts |

ITF adds what none of them needs: probes, because test targets are physical and their state changes outside
the tool.
