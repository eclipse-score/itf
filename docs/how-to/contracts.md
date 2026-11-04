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

# Use, define and enforce contracts

Contracts are your project's own. A contract is **whatever name two parts agree on**: a factory fulfils
`exec.command`, a test or another part expects `exec.command`, and ITF checks that the shapes they publish and
expect fit. ITF ships no vocabulary you must follow; it is the platform that lets a project **discover** its
contracts (`itf contracts map`), **define** them (a definition file, optional) and **enforce** its rules
as a supported set, not a standard. The reasoning is in
[the decision record on target composition](../decisions/DR-002-arch-target-composition.md); the worked example is
`examples/examples/vendor_contract`. The words are defined in the glossary of
[the model](../concepts/model.md#the-vocabulary).

## Names

A contract name is any string two parts agree on: `exec.command`, `platform.up`, `acme/power.relay`,
`acme/led`. `@major` after a capability name pins a major (`acme/power.relay@1`): the provider must explicitly
offer that major, checked by preflight and policy. State `@major` is part of the exact full runtime token:
no stripping or implicit latest. Actions, goals, relations and `reach` use that same token; reports retain its
major. Whether a contract is a capability or a state comes from the part: a factory fulfils a capability
contract, an action makes a state contract true. Roles are named by the target file (`command`, `power`); a
definition may suggest one.

The definition's integer `version` is the latest compatibility major documented there. A provider may offer an
older major if it still satisfies the definition's required shape; consumers that pin `@major` are checked against
the offered majors by planning, test gating and `itf versions check`. Package and pack release versions are
separate; see [Version reporting](versioning.md).

## Use a contract in a test

```python
from typing import Protocol
import score.itf as itf

class Command(Protocol):
  __contract__ = "exec.command"

  def exec(self, command: str) -> tuple[int, bytes]: ...

@itf.requires("command", shape=Command)
def test_run_a_command(target):
  assert target.command.exec("echo -n hi") == (0, b"hi")
```

The consumer owns the Protocol; `__contract__` supplies the contract and its members describe the calls it uses.
Checks cover call structure, including positional and keyword arguments, not type assignability, return values
or semantics. Older member-name lists (`shape=["exec"]`) remain backward compatible without these checks.

Collection preflight groups exact consumer profiles by scope, role, contract and required major without merging
different signatures. Loose gating deselects incompatible or unknown tests; `--itf-strict-gating` rejects
collection before bring-up for applicable incompatible or unknown APIs. Missing roles/scopes and explicit
contract/major differences remain not applicable and deselected; absent provider-major metadata is unknown for
a pinned major. `--itf-plan` prints the report; full artifacts include `preflight.json`.

Policy `itf_expect = [YourProtocol]` checks every capability offering the contract, in every scope, during
resolution, even without test consumers. It does not require missing contracts. An unversioned baseline covers
all majors; `name@1` covers explicitly offered major 1 and rejects matching providers without major metadata.
Multiple baselines compose; violations reject resolution even in loose mode.

## Discover: `itf contracts map`

```
itf contracts map target.itf.yaml                          # text, on standard output
itf contracts map target.itf.yaml --format json            # for tools (text, json, mermaid or html)
itf contracts map --format html --output contract_map.html      # a browsable page; without a target file: every pack
```

With no target file it maps every pack (`--packs docker,ssh` narrows it); `--tests PATH...` adds the tests to read
and `--definitions DIR` a directory of definitions. This is the **contract map**; ITF's own is generated into
`docs/_generated/catalog.html` and served with these docs.

For every contract name in use, from the loaded parts and tests, it shows who offers it and with which shape,
who needs it and expecting which members, which tests ask for it, whether a definition exists, and every
disagreement: a part expecting a member no offerer has, two definitions of one name, a major nobody offers.
Names with no definition are fine; they are simply listed as undefined.

## Define: a definition file

suite. Start from what is observed:

```
itf contracts new acme/led --from-usage target.itf.yaml
```

The command writes the skeleton itself, to `contracts/acme_led.yaml` (or the file named by `--out`), and never
overwrites an existing file; there is nothing to redirect. A definition looks like this:

```yaml
contracts:
  - contract: acme/power.relay
    kind: capability
    role: power
    version: 1
    stability: experimental
    summary: Switch a power relay on and off and read its state.
    members:
      - name: "on"
        signature: "() -> None"
        semantics: Closes the relay.
      - name: toggle
        signature: "() -> bool"
        semantics: Flips the relay. Optional.
        required: false
    guarantees:
      - A relay starts open (off).
```

Definitions are found in a pack's `contracts/` directory, in a project directory named by
`itf_target(contracts = [...])` or `ITF_CONTRACTS_PATH`, and in an installed distribution with an entry point in
the group `score_itf.contracts`. For the supported ITF set, the layout below separates pack references
from shared definitions. Fields: `contract`, `kind` (capability or state), `version`, `summary`,
`description`, `members` (`name`, `signature`, `semantics`, `required`), `guarantees`, `role`, `stability`
contract makes a plan warn, naming `replaced_by`.

Without a definition a target file still compiles: wiring and gating use names, and the no-trust checks use the
shapes the parts publish and expect.

### Shared definitions and pack manifests

The shared contract library owns the full specifications in
`score/itf/contracts/definitions/<contract-id>.yaml`. Each file contains `contracts:` with exactly one entry;
for example, `exec.command.yaml` contains the specification for `exec.command`. Sharing a specification does
not make any provider pack its owner.

Every built-in pack uses the same manifest layout:
`score/itf/packs/<pack>/contracts/<contract-id>.yaml`. Each manifest file contains only a reference to that
contract's canonical definition. For example, each pack declaring `exec.command` uses:

```yaml
$ref: ../../../contracts/definitions/exec.command.yaml
```

There is one file per contract on both sides: no area-level bundles of full specifications in a pack and no
copied specifications for different providers. Pack manifests cover the contracts the pack uses and may also
expose available definitions beyond its active providers. They do not own or redefine those contracts.
Project and vendor definitions remain optional and independently authored; no global registry is required.

The resolution rules for this layout are:

- Resolve each `$ref` relative to the parent directory of the file that declares it, including nested
  references. Never resolve it relative to a policy file or the invocation working directory.
- Load a canonical physical file only once when it is reached repeatedly, including through different paths
  or pack manifests. Deduplicate by physical file identity, not by contract name; retain the canonical file
  as the definition's stable source.
- Keep independently authored definitions of the same contract as duplicates, subject to the existing
  duplicate-definition validation. References must not hide conflicting definitions.
- `$ref` must stand alone in its YAML document; it cannot be combined with `contracts:` or other fields.
  Cycles, missing referenced files and malformed documents or references must produce errors.

Each built-in pack's BUILD data includes both its local manifest references and the canonical definitions
they reach. When packaging a wheel, include both trees and preserve their relative layout. This repository
has no wheel configuration; this is packaging guidance, not a claim of built-wheel validation. See
[Write a pack](plugins.md#build).

## Enforce: `itf contracts check`

```yaml
# rules.yaml
namespaces:
  - acme                    # contracts in this namespace (acme/...) need a definition
roles:
  power: acme/power.relay   # the role `power` is always an acme/power.relay
forbid_stability:
  - deprecated              # no target file may use a deprecated contract
```

```
itf contracts check --rules rules.yaml target.itf.yaml      # exit 1 on violations, for pipelines
itf contracts check --rules rules.yaml a.itf.yaml b.itf.yaml     # any number of target files
```

`itf contracts reference --output docs/reference/contracts.md` writes the Markdown reference of the defined contracts.

## Version and deprecate

A change that removes or changes a member is a new major: a new name with `@2` for the offering side, and the
old definition marked `stability: deprecated` with `replaced_by`. Plans warn about deprecated contracts and a
contract rules can forbid them. Adding an optional member (`required: false`) does not change the major; tests that need
it say so with `shape`.

## Propose a contract for the ITF supported set

Propose a single-entry definition in the shared library's
`score/itf/contracts/definitions/<contract-id>.yaml` and a standalone reference in each relevant pack's
that fulfil the contract. Open a pull request with the definition, pack references and packaging data, the
it (use the contract proposal template).
