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

# score.itf.contracts: the optional contract library

ITF itself knows no contracts: a contract is any name two parts agree on (`exec.command`). This package is what a
project uses when it wants more than the name: definitions with members and guarantees, a map of what is in use,
rules, and conformance checks. Nothing in the core imports it; packs may not import it either (they declare their
own Protocols). The command line and the conformance runs do.

| Module | Holds |
|---|---|
| `__init__.py` | definition loading and merging; see the layout below for shared specs and pack references |
| `usage.py` | the contract map: every contract in use, from loaded factories, actions and tests, with disagreements |
| `inventory.py` | the map as plain data, the input of the renderers |
| `render.py` | text, JSON, Mermaid, the HTML contract map and the Markdown reference |
| `rules.py` | a project's rules over contracts (`itf contracts check --rules`) |
| `run.py`, `conformance/`, `pytest_conformance.py` | conformance checks: what a provider must do to honour a contract, run per target |

From the command line: `itf contracts map | reference | new --from-usage | check --rules`
(`score/itf/cli/README.md`). How to write a definition: `docs/how-to/contracts.md`.

## Shared definition ownership

The shared library owns `score/itf/contracts/definitions/<contract-id>.yaml`, one full specification
per file, with exactly one entry under `contracts:`. No pack owns a shared specification.

Every pack keeps the definitions of the contracts it uses in its own `contracts/` directory,
`score/itf/packs/<pack>/contracts/<contract-id>.yaml`. For a shared definition that file is a symlink to
`definitions/<contract-id>.yaml`, so there is one text to change and each pack is still complete on its own.
Project and vendor packs keep plain files there; no global registry is required. A file reached twice through
symlinks is loaded once; two different files defining the same contract are duplicates, which the contract map
reports. See [the contract guide](../../../docs/how-to/contracts.md#shared-definitions-and-pack-manifests).
