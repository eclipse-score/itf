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

| Module | Holds |
|---|---|
| `__init__.py` | definition loading and merging; see the layout below for shared specs and pack references |
| `usage.py` | the contract map: every contract in use, from loaded factories, actions and tests, with disagreements |
| `inventory.py` | the map as plain data, the input of the renderers |
| `render.py` | text, JSON, Mermaid, the HTML contract map and the Markdown reference |
| `rules.py` | a project's rules over contracts (`itf contracts check --rules`) |

From the command line: `itf contracts map | reference | new --from-usage | check --rules`
(`score/itf/cli/README.md`). How to write a definition: `docs/how-to/contracts.md`.

## Shared definition ownership

The shared library owns `score/itf/contracts/definitions/<contract-id>.yaml`, one full specification
per file, with exactly one entry under `contracts:`. No pack owns a shared specification.

Every built-in pack declares contract metadata through local manifest files at
`score/itf/packs/<pack>/contracts/<contract-id>.yaml`, each containing only:

```yaml
$ref: ../../../contracts/definitions/<contract-id>.yaml
```

These references cover the contracts each pack uses and may also expose available definitions beyond its
active providers. Project and vendor definitions remain optional and independently authored, including full
specifications in their own `contracts/` directories; no global registry is required.

References must resolve relative to the declaring file's parent, never a policy directory or working
directory. Repeated references to the same canonical physical file load it once and retain that file as the
definition's stable source; distinct authored files
defining the same contract remain duplicates under the existing validation. `$ref` must be standalone;
cycles, missing files and malformed documents or references must produce errors.

Each built-in pack's BUILD data bundles its local references and their canonical definitions. When packaging
a wheel, include both trees with their relative layout intact. This repository has no wheel configuration;
this is packaging guidance, not a claim of built-wheel validation. See
[the contract guide](../../../docs/how-to/contracts.md#shared-definitions-and-pack-manifests) for details.
