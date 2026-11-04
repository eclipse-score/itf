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
| `__init__.py` | definitions: YAML files (`contracts/*.yaml` in a pack, or a project's), loaded and merged |
| `usage.py` | the contract map: every contract in use, from loaded factories, actions and tests, with disagreements |
| `inventory.py` | the map as plain data, the input of the renderers |
| `render.py` | text, JSON, Mermaid, the HTML contract map and the Markdown reference |
| `rules.py` | a project's rules over contracts (`itf contracts check --rules`) |

From the command line: `itf contracts map | reference | new --from-usage | check --rules`
(`score/itf/cli/README.md`). How to write a definition: `docs/how-to/contracts.md`.
