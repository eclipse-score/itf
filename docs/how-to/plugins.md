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

# Write a pack

A pack is a directory holding parts: capability factories (`@capability`) and actions (`@state`). A target file
names them by label (`<pack>.<name>`); tests reach them only through roles. A pack is optional: code in a
project's own policy is the pack `local` and works the same way. The words are defined in the glossary of
[the model](../concepts/model.md#the-vocabulary).

## Layout

```
score/itf/packs/<pack>/
  pack.yaml        name, version, prerequisites
  __init__.py      one-line description
  <topic>.py       implementation: classes, config dataclasses, the Protocols they expect
  providers.py     the @capability factories only: import from topic modules, declare
  steps.py         the @state actions and their probes only
  plugin.py        pytest_plugins = ["...providers", "...steps"]   (the entry point)
  contracts/       one <contract-id>.yaml reference per declared contract (built-in packs)
  README.md        the label table, host prerequisites and a target file excerpt
  BUILD            py_library(name = "lib") + py_itf_plugin
```

Group multiple backends by responsibility, not by old versus new APIs. Keep protocol
code independent of sockets and process lifecycle, and keep registration in providers
and actions. A small pack with already distinct topic modules need not gain subpackages.

The built-in packs follow these boundaries:

| Pack | Implementation boundaries |
|---|---|
| `dlt` | `receive/`: host process and recorded windows; `on_target/`: dlt-receive run on the target (`dlt.on_target`) |
| `ping` | `ping.py`: canonical command API; `icmp/`: socket probing and configured reachability monitoring |
| `docker` | platform lifecycle, endpoint, commands, files and processes |
| `localhost` | host platform, commands, files and processes |
| `ssh` | connected session, commands, file transfer and remote processes |
| `qemu` | emulator configuration, platform lifecycle and descriptors |
| `serial` | serial console, PTY console and command adapter |
| `pcap` | capture implementation and separately labelled host/target start actions |
| `net` | endpoint and credential descriptors |
| `core_dump` | command/files-backed collector; explicit invocation, no automatic teardown |
| `sim` | in-memory platform, shell, log and packet backends, grouped by simulated service |

Canonical objects live in the pack. The original import paths outside the packs
(`score.itf.core.com`, `score.itf.plugins.dlt`, ...) only re-export them, and carry no
other implementation (`//test/integration/legacy:shims_test`). Project fixtures belong in
`conftest.py`, not inside a pack entrypoint.

`pack.yaml` carries what tools read: the pack's `name` (the first segment of every label), `version` and
`prerequisites` (host requirements, read by `itf doctor`).

```yaml
name: docker
version: 0.1.0
prerequisites:
  - a Docker-compatible daemon (DOCKER_HOST for Podman)
```

A pack is loaded from a label: the module `score.itf.packs.<name>.plugin`, or, for a pack outside the ITF
repository, an entry point of the group `score_itf.packs` (`acme = acme.plugin`). A vendor's distribution adds
`score_itf.contracts` for its definitions (see `examples/examples/vendor_contract`).

Authored target files also declare their pack entrypoints explicitly:

```yaml
packs:
  docker: score.itf.packs.docker.plugin
  ssh: score.itf.packs.ssh.plugin
```

Includes inherit these maps. An override adds the packs its new parts use; an
include-only target file does not need to repeat its base target's declarations.
Project parts labelled `local.<name>` are not an installed pack.

## Factories

```python
@capability("exec.command")                   # the contract this factory fulfils; label <pack>.exec
def exec(platform: Platform) -> DockerExec:   # a slot: the factory's own Protocol with __contract__
    return DockerExec(platform)

@capability("platform.instance", label="platform")
def make_platform(config: PlatformConfig) -> Iterator[DockerPlatform]:   # a generator: teardown after yield
    platform = DockerPlatform(config)
    yield platform
    platform.stop()
```

- The return annotation is what the factory publishes: a class (often your own Protocol) whose members are the shape.
- A slot is a parameter annotated with a class that sets `__contract__`; the class's members are the shape the
  factory expects. Never import another pack: write your own Protocol with only the members you use.
- `config: <dataclass>` is the settings schema (`with:` in a target file); a typo fails at plan time with the
  role named. Mark a secret field `field(metadata={"sensitive": True})`, or a whole factory
  `@capability(..., sensitive=True)` (a login, a token): ITF never shows its values, in plans, reports or logs.
- Constructing starts nothing. Starting is an action's job.
- `@major` after a contract name (`"exec.command@1"`) says which major the factory fulfils, or a slot expects;
  when both sides give one they must agree.

## Actions

```python
@state("platform.up", label="start")
def start_platform(platform: Platform) -> None:
    platform.start()

@start_platform.probe
def platform_is_up(platform: Platform) -> bool:
    return platform.running()

@state("shell.open", also=("network.reachable",), label="open")
def open_session(shell: Shell) -> None:
    shell.connect()

@open_session.probe_for("network.reachable")
def is_reachable(shell: Shell) -> bool: ...
```

- The probe takes the same slots as the action and decides whether the state holds; it must be cheap, safe to
  repeat and never change anything.
- `after=` lists states that must hold first; `breaks=` lists states the action destroys; `also=` lists further
  states the one action makes true, each with its own `probe_for`.
- **A pack states no ordering that depends on another pack.** `ssh.open` does not say `after=("platform.up",)`,
  because it cannot know whether `platform.up` comes from the docker pack, the qemu pack or the lab: the
  target file says it with `relations:`. Use `after=` only for states the action itself needs, such as the
  state of its own slots.
- Two actions that make the same state true are fine; a target file picks one with `by:`.
- An action is a candidate in a scope only if all its slots can be filled there; when a slot has several
  candidates the target file chooses with `actions:` and `bind:`.

## Conformance and definitions

Every built-in pack uses the same local manifest layout, not its own copies of shared specifications.
Each `score/itf/packs/<pack>/contracts/<contract-id>.yaml` contains only:

```yaml
$ref: ../../../contracts/definitions/<contract-id>.yaml
```

The shared library owns `score/itf/contracts/definitions/<contract-id>.yaml`, with exactly one entry under
`contracts:` per file. Pack manifests cover the contracts a pack uses and may also expose available
definitions beyond its active providers; they do not confer ownership of those definitions. This applies
uniformly even when a contract currently has only one provider. External packs may keep optional,
independently authored full specifications in their own `contracts/` directories; no global registry is
required. The canonical definition may name a
`conformance:` module whose `CHECKS` (keyed by contract name) hold the checks:

```python
@check()
def a_failing_command_reports_its_exit_code_without_raising(node):
    code, _ = node.exec("sh -c 'exit 3'")
    expect(code == 3, f"exit code was {code}")   # raises with the message when the condition is false
```

`//score/itf/contracts:conformance` runs every check against every part of a target that claims the contract.
See [Use, define and enforce contracts](contracts.md#shared-definitions-and-pack-manifests) for the required
declaring-file-relative reference resolution, physical-file deduplication, duplicate-definition handling and
reference errors.

## BUILD

Every built-in pack's BUILD bundles both its local references and the canonical definition files they reach
as data. The following is schematic: `canonical_contract_data` stands for the list of Bazel
data labels for those shared files, not a new predefined rule or target.

```starlark
py_library(name = "lib", srcs = glob(["**/*.py"]) + ["//score/itf/packs:init"],
           data = ["README.md", "pack.yaml"] + glob(["contracts/*.yaml"]) + canonical_contract_data,
           deps = ["//score/itf/contracts", "//score/itf/core"])
py_itf_plugin(name = "<pack>", pack = "<pack>", enabled_plugins = ["score.itf.packs.<pack>.plugin"], py_library = ":lib")
```

Bundling only `contracts/*.yaml` is insufficient: those files are references, not the full specifications.
When packaging a wheel, include both `score/itf/packs/*/contracts/*.yaml` and
`score/itf/contracts/definitions/*.yaml`, preserving the relative paths used by `$ref`. This repository has no
wheel configuration; this is packaging guidance, not a claim of built-wheel validation.

`pack =` is the pack's name, the first part of its labels: an `itf_target` reads the pack names of its `packs`
from it.

Binaries a pack runs are built by Bazel and found through runfiles (see the dlt and pcap packs). Add unit tests
under `test/packs/`, and a target file for the pack to `test/integration/targets/` so the generic suite runs
on it. Write the pack's README by hand: the label table, host prerequisites and a target file excerpt.
