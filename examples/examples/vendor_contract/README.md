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

# A vendor's own contract

Acme sells a power relay and wants tests, its customers' and its own, to switch it the same way whatever the
hardware. It defines a contract, `acme/power.relay`, and ships it. **Nothing registers the name**: a contract is
whatever name two parts agree on. ITF lets Acme define it, check it and map it.

```
acme_pack/                      what Acme ships
  acme/
    pack.yaml                   the pack's name: acme
    plugin.py                   the pack's entrypoint module
    providers.py                capability factories: one fulfilling acme/power.relay (a simulation)
targets/                        what ITF reads
  target.itf.yaml               a target file with the relay as the role `power`
  policy.py                     the project's own part: a status LED, contract `bench/led`, never defined
test_relay.py                   tests that require the roles
```

In a pack, `providers.py` holds the capability factories and `steps.py` the actions (this pack has no actions).

## 1. The factory says what it fulfils

```python
@capability("acme/power.relay@1")
def simulated_relay() -> SimulatedRelay:
    return SimulatedRelay()
```

The decorator is the one place that says which contract, and which major, the factory fulfils. The label is the
pack plus the function name: `acme.simulated_relay`. What the factory publishes (`on`, `off`, `is_on`, `toggle`)
is read from its return annotation. A factory for real hardware fulfils the same contract; the tests do not change.

## 2. The definition is optional, and the vendor's

`acme_pack/acme/contracts/power.yaml` gives the contract meaning: summary, members with signatures, guarantees,
is `required: false`: a factory may omit it, and a test that needs it says so with `shape`. Without this file
the target file still compiles: wiring and gating use the names and the shapes the parts publish and expect. A

This vendor example keeps its independently authored definitions in its own `contracts/` directory. That
does not make a provider pack the owner of ITF's shared specifications: the built-in pack layout
uses [shared-library definitions and per-pack references](../../../docs/how-to/contracts.md#shared-definitions-and-pack-manifests),
without requiring vendors to move their definitions into a global registry. ITF also reads the directories of
`ITF_CONTRACTS_PATH`, which `py_itf_test(contracts = [...])` sets (this example), and distributions with a
`score_itf.contracts` entry point.

## Where the pack comes from

ITF's own packs are found by name. A pack that is not installed is located by the target file itself, in one
explicit line:

```yaml
packs:
  acme: acme.plugin
```

Once Acme publishes its pack as a distribution with a `score_itf.packs` entry point, that line can go.

## 3. A target file and a test use the role

```yaml
packs:
  acme: acme.plugin
policies:
  - examples/vendor_contract/targets/policy.py
capabilities:
  power: acme.simulated_relay
  led: local.status_led
```

```python
from typing import Protocol

import score.itf as itf

class Relay(Protocol):
  __contract__ = "acme/power.relay@1"

  def on(self) -> None: ...
  def off(self) -> None: ...
  def is_on(self) -> bool: ...

@itf.requires("power", shape=Relay)
def test_the_relay_switches(target):
  target.power.off()
  assert not target.power.is_on()
    target.power.on()
    assert target.power.is_on()
  target.power.off()
```

`@1` pins the major (a test that asks for another is deselected with the reason). A separate consumer Protocol
declares `off()` and the optional `toggle()` for the toggle test, without requiring it for the base relay test.
The independent LED test has its own Protocol; there is no common module role across these three tests.
Swapping the simulation for a real relay is changing the factory label.

## 4. The vendor's checks

against every part of the target that claims `acme/power.relay`: the simulation here, a customer's hardware
factory in their pipeline.

## 5. See what is in use

Run from the `examples/` MODULE root, with the example's `acme_pack` on the Python import path for direct
CLI use (`PYTHONPATH=examples/vendor_contract/acme_pack`). The YAML policy path is relative to this working
directory, not the YAML parent. Bazel bundles the selected module in `itf_target.srcs`; it does not select
policies. There is no native directory discovery.

```
itf contracts map examples/vendor_contract/targets/target.itf.yaml
itf contracts new acme/power.relay --from-usage examples/vendor_contract/targets/target.itf.yaml
itf contracts check --rules examples/vendor_contract/rules.yaml examples/vendor_contract/targets/target.itf.yaml
```

For this target file the map shows two contracts that matter here:

| Contract | Offered by (shape) | Needed by | Tests | Defined |
|---|---|---|---|---|
| `acme/power.relay` | `acme.simulated_relay` (`is_on`, `off`, `on`, `toggle`) | none | `test_the_relay_switches`, `test_the_optional_toggle` | yes, `acme/contracts/power.yaml` |
| `bench/led` | `local.status_led` (`light`, `lit`) | none | `test_a_contract_without_a_definition` | no |

Any disagreement (a test requiring a member no offerer has, two definitions of one name, a major nobody offers)
is listed under its contract. `contracts new` writes the skeleton for `bench/led` from the shapes observed (into `contracts/`, or the file
named by `--out`; it never overwrites), if the project later wants it defined. Contract rules (`rules.yaml`) can require definitions for a namespace, fix a role to a contract (the role `power` is
always an `acme/power.relay`) and forbid stabilities:

```yaml
namespaces:
  - acme
roles:
  power: acme/power.relay
forbid_stability:
  - deprecated
```

```
bazel build //examples/vendor_contract:target                                    # target.plan.json
```
