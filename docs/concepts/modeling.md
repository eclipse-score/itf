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

# Modeling a target

How to decide what to write where. Short rules; every word is defined in the glossary of [the model](model.md#the-vocabulary).

## Decide what each fact is

| Fact | It is | Written as |
|---|---|---|
| a thing tests use (a command runner, a console, a log stream) | a capability | a factory, `@capability("<contract>")` |
| a condition that is made true and checked (the container runs, the session is open) | a state | an action with a probe, `@state("<state>")` |
| what a target is made of | a target file | `capabilities:` by role |
| what you want true when the target is up | a goal | a state under `goals:` |
| something that holds without ITF (the rack is powered) | an assumption | `assume:` with an owner and a reason |
| an order between states that no part knows about | a relation | `relations:` with `after:` and `breaks:` |
| a value that differs per setup | a setting | an override file |
| a check that needs code | project code | `itf_verify` in the policy |

## Design a capability

- Name the contract after what a test does with it, not after the machine: `exec.command`, not `docker.run`.
- Publish what the object offers by its return type; members starting with `_` are not part of the shape.
- Take what you need through slots: a parameter annotated with **your own** Protocol that sets `__contract__`
  and lists only the members you use. Never import another pack.
- Settings go in a frozen dataclass named `config`. Every field has a type; secrets are marked.
- Construction starts nothing. Starting is an action's job, so the plan can order and verify it.

## Design a state

- One action makes the state true; its probe says whether it holds, and is cheap and safe to repeat.
- `after=` lists what must hold first; `breaks=` lists what the action destroys (a restart breaks
  `network.reachable`). Only name states the action itself depends on: an ordering between your action and another
  pack's belongs to the target file (`relations:`), because the pack cannot know which other packs are listed.
- Several states from one action: `also=` with a probe per state (`@action.probe_for("network.reachable")`).
- Never let a probe change anything.

## Choose roles and scopes

- A role is the name tests use. Use the contract's usual name (`command`, `files`, `console`) unless a target
  has two of the same kind (`console` and `debug`).
- Two candidates for one slot of a factory: `bind:` on the role says which role the slot uses.
- Two candidates for one slot of an action: `actions:` with `bind:` says which role the slot uses.
- Two actions that could make one state true: `by:` on the goal says which.
- An order between states that the actions do not state: `relations:`.
- One device is one scope: `scopes: gw:` with its own roles, `share:` for the root roles it uses.

## Project parts

Code in the project's policy (`policy.py`) belongs to the pack `local`: the label is `local.<function>`. Use it for
what is specific to this project and does not deserve a pack: waiting for a daemon, a status LED. A project
action is always considered when planning, if all its slots can be filled in the scope: if it makes a state true
that a pack's action also makes true, every target file that uses the state names one with `by:`.

## Quick review before adopting a pack

1. Read its README: label table, prerequisites, target file excerpt.
2. `itf validate` a target file with it; read the plan.
3. Run `itf contracts map`: which names does it offer and expect, and do your tests agree?
4. Run its conformance checks against your own fulfilling parts.
