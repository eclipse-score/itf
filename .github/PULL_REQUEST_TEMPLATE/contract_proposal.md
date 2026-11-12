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

<!-- Use this template for a pull request that adds or changes a contract definition ITF supports (in the shared
      contract library, referenced by pack manifests). ITF knows no contracts: any name
      works without a definition. Definitions are the supported set the ITF team maintains, with conformance
      checks. Guide: docs/how-to/contracts.md. -->

## Contract

Name: `<area>.<name>`  (a capability contract, fulfilled by capability factories, or a state contract, made true by actions; see the glossary in docs/concepts/model.md)
Suggested role: `<one lowercase word>`  (capabilities only: the role target files give it, `target.<role>`)
Version: 1
Stability: experimental

## Problem

What should a test be able to do that it cannot do today, or can only do with code tied to one platform?
Which tests need it, and which target files would provide it? Why is no existing contract enough?

## Definition

- [ ] `score/itf/contracts/definitions/<contract-id>.yaml` has exactly one entry under `contracts:`: summary,
      description, members with signature and semantics, guarantees, `see_also`, `conformance`. Block style only.
- [ ] Each relevant pack has `score/itf/packs/<pack>/contracts/<contract-id>.yaml` containing only
      `$ref: ../../../contracts/definitions/<contract-id>.yaml`; the shared library owns the specification.
- [ ] Each relevant pack's BUILD data bundles the local references and canonical definitions.
      When packaging a wheel, include both trees, preserving relative paths. This repository has no wheel
      configuration; this instruction is not a claim of built-wheel validation.
- [ ] Every member is required unless a real factory cannot offer it; optional members say how a test
      gates on them (`shape=`).
- [ ] The text says what a test must not rely on.
- [ ] `itf contracts map` shows no disagreement for the name, and `itf contracts check --rules tools/contract_rules.yaml`
      exits 0 (add the new namespace to the rules if it has one).
- [ ] The contract map (`bazel run //score/itf/cli:itf -- contracts map --format html --output docs/_generated/catalog.html`) and
      the reference (`bazel run //score/itf/cli:itf -- contracts reference --output docs/reference/contracts.md`) were
      regenerated.

## Conformance checks

Which checks in the pack's `conformance_<area>.py` hold a factory to each guarantee? List them, or
say why a guarantee cannot be checked. `itf contracts check --rules <file> --conformance <target file>`
runs them against a target file.

## Capability factories and actions

A contract needs both, in this pull request or linked:

- [ ] At least one **real** part (a capability factory or an action: hardware, a daemon, a real service): its label.
- [ ] At least one **simulation** that behaves like the device, not a stub that accepts calls: its label.
- [ ] Both pass the conformance checks (`bazel test //test/integration:conformance_...`).
- [ ] Each declares the contract it keeps (`@capability("<area>.<name>@1")`, `@state("<area>.<name>")`).

## Owners

Who maintains the definition and answers questions about it? Name at least two people or a team.

## Versioning

- [ ] New contract, or: this change adds an optional member only (the major stays).
- [ ] A removal, a required member added, or a changed meaning is a new major and is explained here.
- [ ] A contract this replaces is marked `deprecated` with `replaced_by`.
