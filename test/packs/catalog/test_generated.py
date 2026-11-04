# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************
# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
"""The docs site serves the contract map and the contracts reference as checked-in files, generated from the
packs' code and definitions. These tests fail when a checked-in copy is stale, and when the supported packs
disagree with each other or with their own definitions."""

from pathlib import Path

import pytest
import yaml

from score.itf import contracts
from score.itf.contracts import inventory, render

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def data():
    packs = inventory.known_packs()
    catalog, errors = inventory.load_catalog(packs)
    return inventory.inventory(catalog, errors=errors, packs=packs)


def test_every_pack_loads_and_the_supported_set_agrees_with_itself(data):
    assert data["errors"] == []
    assert [d for c in data["contracts"] for d in c["disagreements"]] == []


def test_every_contract_the_packs_use_is_defined(data):
    assert [c["contract"] for c in data["contracts"] if c["definition"] is None] == []


def test_every_pack_uses_individual_references_to_individual_canonical_contracts():
    canonical = Path(contracts.__file__).parent / "definitions"
    definitions = {}
    for path in canonical.glob("*.yaml"):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert len(document["contracts"]) == 1, path
        name = document["contracts"][0]["contract"]
        assert path.stem == name and name not in definitions, path
        definitions[name] = path
    assert definitions
    referenced = set()
    for name in inventory.known_packs():
        directory = inventory._pack_location(name) / "contracts"
        paths = sorted(directory.glob("*.yaml"))
        assert paths, f"{name} has no contract manifest"
        catalog, errors = inventory.load_catalog([name])
        assert not errors
        used = set(contracts.contract_map(catalog))
        available = {path.stem for path in paths}
        assert used <= available, name
        for path in paths:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert set(document) == {"$ref"}, path
            assert (directory / document["$ref"]).resolve() == definitions[path.stem].resolve(), path
        assert {item.contract for item in contracts.read_directory(directory)} == available, name
        referenced.update(available)
    assert referenced == definitions.keys()
    loaded = contracts.load_list()
    assert len(loaded) == len({item.contract for item in loaded})


def test_the_marketplace_page_is_the_contract_map(data):
    expected = render.render_html(data)
    checked_in = (ROOT / "docs/_generated/catalog.html").read_text(encoding="utf-8")
    assert checked_in == expected, (
        "regenerate: bazel run //score/itf/cli:itf -- contracts map --format html --output docs/_generated/catalog.html"
    )


def test_the_contracts_reference_is_generated_from_the_definitions(data):
    expected = render.render_reference(data)
    checked_in = (ROOT / "docs/reference/contracts.md").read_text(encoding="utf-8")
    assert checked_in == expected, (
        "regenerate: bazel run //score/itf/cli:itf -- contracts reference --output docs/reference/contracts.md"
    )


def test_the_page_lists_contracts_factories_actions_and_packs(data):
    page = render.render_html(data)
    for section in ('id="contracts"', 'id="factories"', 'id="actions"', 'id="packs"'):
        assert section in page
    assert "docker.platform" in page and "platform.up" in page and 'id="p-ssh"' in page
