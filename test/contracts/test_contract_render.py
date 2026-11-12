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
"""What a person reads: the contract map as text, Mermaid and one HTML page, and the Markdown reference.

The inventory below is written out by hand (the shape `inventory.inventory` returns), so every line of every
output can be traced to a field: one defined capability contract with everything filled in, one undefined,
one defined state contract, a factory, an action, a pack and an error.
"""

import pytest

from score.itf.contracts import render

RELAY = {
    "contract": "acme/power.relay",
    "kind": "capability",
    "offered_by": [{"label": "local.relay", "shape": ["read", "switch"], "major": 1}],
    "needed_by": [
        {"label": "local.rack", "slot": "relay", "expects": ["switch"], "major": None},
        {"label": "local.lab", "slot": "relay", "expects": [], "major": 2},
    ],
    "tests": [
        {"test": "t.py::test_a", "role": "relay", "shape": ["switch"]},
        {"test": "", "role": "relay2", "shape": []},
    ],
    "defined": True,
    "disagreements": [{"kind": "major-mismatch", "message": "local.lab expects acme/power.relay@2, offered: @1"}],
    "definition": {
        "version": 1,
        "kind": "capability",
        "summary": "A switchable relay.",
        "description": "Long text about relays.",
        "role": "relay",
        "stability": "stable",
        "replaced_by": "acme/power.relay2",
        "conformance": "acme.conformance",
        "see_also": ["acme/power.on"],
        "probe": "The relay answers read().",
        "guarantees": ["switch is idempotent"],
        "members": [
            {"name": "switch", "signature": "(on: bool)", "semantics": "turns it on or off", "required": True},
            {"name": "read", "signature": "()", "semantics": "its state", "required": False},
        ],
        "source": "score/itf/packs/acme/contracts: defs.yaml",
    },
    "checks": ["relay_switches"],
}
OPAQUE = {
    "contract": "acme/bench.rack",
    "kind": "capability",
    "offered_by": [],
    "needed_by": [],
    "tests": [],
    "defined": False,
    "disagreements": [],
    "definition": None,
    "checks": [],
}
ON = {
    "contract": "acme/power.on",
    "kind": "state",
    "offered_by": [{"label": "local.power_on", "shape": [], "major": None}],
    "needed_by": [],
    "tests": [],
    "defined": True,
    "disagreements": [],
    "definition": {
        "version": 3,
        "kind": "state",
        "summary": "Power is on.",
        "description": "d",
        "role": "",
        "stability": "experimental",
        "replaced_by": "",
        "conformance": "",
        "see_also": [],
        "probe": "",
        "guarantees": [],
        "members": [],
        "source": "elsewhere/defs.yaml",
    },
    "checks": [],
}
INV = {
    "packs": [
        {
            "name": "acme",
            "version": "1.2",
            "summary": "Acme parts.",
            "prerequisites": ["a tool"],
            "factories": ["local.relay"],
            "actions": ["local.power_on"],
        }
    ],
    "contracts": [OPAQUE, ON, RELAY],
    "factories": [
        {
            "label": "local.relay",
            "pack": "acme",
            "contract": "acme/power.relay",
            "major": 1,
            "shape": ["read", "switch"],
            "needs": [{"slot": "bus", "contract": "acme/bus", "expects": ["send"], "major": 2}],
            "config": [
                {"name": "port", "type": "int", "required": True, "sensitive": False},
                {"name": "host", "type": "str", "required": False, "sensitive": False, "default": "lo"},
                {"name": "key", "type": "str", "required": False, "sensitive": True},
            ],
            "teardown": True,
            "observes": "no",
        }
    ],
    "actions": [
        {
            "label": "local.power_on",
            "pack": "acme",
            "state": "acme/power.on",
            "also": ["acme/power.up"],
            "after": ["acme/power.ready"],
            "breaks": [],
            "probe": True,
            "uses": [{"slot": "relay", "contract": "acme/power.relay", "expects": ["switch"]}],
        },
        {
            "label": "local.blind",
            "pack": "acme",
            "state": "acme/power.up",
            "also": [],
            "after": [],
            "breaks": [],
            "probe": False,
            "uses": [],
        },
    ],
    "errors": ["pack ghost could not be loaded: ImportError: no"],
}


def lines_of(text):
    return text.splitlines()


def test_text_lists_each_contract_with_who_offers_needs_and_tests_it_and_where_they_disagree():
    text = render.render_text(INV)
    assert lines_of(text) == [
        "acme/bench.rack  [capability]  not defined",
        "",
        "acme/power.on  [state]  defined v3 (experimental)",
        "  offered by local.power_on: -",
        "",
        "acme/power.relay  [capability]  defined v1 (stable)",
        "  offered by local.relay@1: read, switch",
        "  needed by  local.rack (relay): expects switch",
        "  needed by  local.lab (relay) @2",
        "  test       t.py::test_a (role relay): switch",
        "  test       relay2 (role relay2): -",
        "  DISAGREES  major-mismatch: local.lab expects acme/power.relay@2, offered: @1",
        "",
        "3 contracts, 1 without a definition, 1 disagreements",
        "error: pack ghost could not be loaded: ImportError: no",
    ]


def test_text_of_an_empty_inventory_is_just_the_totals():
    assert render.render_text({"contracts": [], "errors": []}) == "0 contracts, 0 without a definition, 0 disagreements"


def test_mermaid_draws_contracts_as_nodes_offers_as_solid_edges_and_needs_as_dashed_slot_edges():
    assert lines_of(render.render_mermaid(INV)) == [
        "flowchart LR",
        '  c_acme_bench_rack[["acme/bench.rack"]]',
        '  c_acme_power_on(["acme/power.on"])',
        '  c_acme_power_relay[["acme/power.relay"]]',
        '  p_local_power_on["local.power_on"] --> c_acme_power_on',
        '  p_local_relay["local.relay"] --> c_acme_power_relay',
        '  c_acme_power_relay -.->|relay| p_local_rack["local.rack"]',
        '  c_acme_power_relay -.->|relay| p_local_lab["local.lab"]',
    ]


def test_render_picks_the_format_and_refuses_an_unknown_one():
    assert render.render(INV, "text") == render.render_text(INV)
    assert render.render(INV, "mermaid") == render.render_mermaid(INV)
    assert render.render(INV, "json") == render.render_json(INV)
    assert render.render(INV, "html") == render.render_html(INV)
    with pytest.raises(ValueError, match="format is one of text, json, mermaid, html, not 'pdf'"):
        render.render(INV, "pdf")


def test_html_has_a_card_per_contract_factory_action_and_pack_and_the_counts():
    page = render.render_html(INV, title="My <map>")
    assert "<title>My &lt;map&gt;</title>" in page
    assert "1 packs, 3 contracts, 1 capability factories, 2 actions, 1 disagreements." in page
    for card in (
        "c-acme/power.relay",
        "c-acme/power.on",
        "c-acme/bench.rack",
        "f-local.relay",
        "a-local.power_on",
        "p-acme",
    ):
        assert f'<div class="card" id="{card}">' in page, card
    assert '<div class="card bad">pack ghost could not be loaded: ImportError: no</div>' in page


def test_a_defined_capability_card_shows_definition_members_guarantees_and_everyone_around_it():
    card = _card(render.render_html(INV), "c-acme/power.relay")
    assert '<span class="cap">acme/power.relay</span>' in card
    assert ", v1, stable</span></h3>" in card and "<p>A switchable relay.</p>" in card
    assert "suggested role: <code>relay</code>" in card
    assert "<code>switch(on: bool)</code> (required): turns it on or off" in card
    assert "<code>read()</code> (optional): its state" in card
    assert "<p>Guarantees</p><ul><li>switch is idempotent</li></ul>" in card
    assert "<code>local.relay@1</code> read, switch" in card
    assert "<code>local.rack</code> slot <code>relay</code> expects switch" in card
    assert "<code>local.lab</code> slot <code>relay</code> expects -" in card
    assert "t.py::test_a: role <code>relay</code> switch" in card and "relay2: role <code>relay2</code> -" in card
    assert "<p>Conformance checks</p><ul><li><code>relay_switches</code></li></ul>" in card
    assert '<p class="bad">Disagreements</p><ul><li>local.lab expects acme/power.relay@2, offered: @1</li></ul>' in card


def test_a_state_card_and_an_undefined_card_leave_out_what_they_do_not_have():
    page = render.render_html(INV)
    state = _card(page, "c-acme/power.on")
    assert '<span class="state">acme/power.on</span>' in state and ", v3, experimental</span></h3>" in state
    for absent in (
        "suggested role",
        "<p>Members</p>",
        "<p>Guarantees</p>",
        "<p>Tests</p>",
        "Conformance",
        "Disagreements",
    ):
        assert absent not in state
    assert '<p>Needed by</p><p class="muted">none</p>' in state and "<ul></ul>" not in state
    opaque = _card(page, "c-acme/bench.rack")
    assert ", not defined</span></h3>" in opaque and '<p>Offered by</p><p class="muted">nobody</p>' in opaque
    assert "<code>" not in opaque


def test_an_offerer_whose_label_contains_none_keeps_its_label():
    offered = {**ON, "contract": "acme/x", "offered_by": [{"label": "acme.nonexistent", "shape": [], "major": None}]}
    card = _card(render.render_html({**INV, "contracts": [offered]}), "c-acme/x")
    assert "<code>acme.nonexistent</code>" in card and "nobody" not in card


def test_factory_action_and_pack_cards_state_what_each_one_needs_offers_and_sets():
    page = render.render_html(INV)
    factory = _card(page, "f-local.relay")
    assert 'offers <span class="cap">acme/power.relay@1</span>' in factory and "<p>shape: read, switch</p>" in factory
    assert "slot <code>bus</code>: acme/bus@2 expects send" in factory
    assert "<code>port</code> int required" in factory
    assert "<code>host</code> str default lo" in factory
    assert "<code>key</code> str secret" in factory and "default" not in factory.split("key")[1]
    assert "observed by a later process: no" in factory
    action = _card(page, "a-local.power_on")
    assert 'makes <span class="state">acme/power.on</span> true' in action
    assert "after: acme/power.ready; breaks: -; also: acme/power.up; probe: yes (skippable when it holds)" in action
    assert "slot <code>relay</code>: acme/power.relay" in action
    assert "probe: no (always runs)" in _card(page, "a-local.blind")
    pack = _card(page, "p-acme")
    assert "<p>Acme parts.</p><p>Factories: local.relay</p><p>Actions: local.power_on</p>" in pack
    assert "<li>a tool</li>" in pack


def _card(page: str, card_id: str) -> str:
    start = page.index(f'<div class="card" id="{card_id}">')
    return page[start : page.index("</div>", start)]


def test_the_reference_indexes_and_describes_only_the_defined_contracts():
    text = render.render_reference(INV)
    assert text.startswith("<!--") and text.endswith("\n") and not text.endswith("\n\n")
    index = [ln for ln in lines_of(text) if ln.startswith("| `")]
    assert index == [
        "| `acme/power.on` | state | experimental | Power is on. |",
        "| `acme/power.relay` | capability | stable | A switchable relay. |",
    ]
    assert "acme/bench.rack" not in text.split("## Index")[1]


def test_a_reference_section_has_the_definition_members_probe_and_who_makes_it_true():
    relay = _section(render.render_reference(INV), "acme/power.relay")
    assert relay.splitlines()[:3] == [
        "## `acme/power.relay`",
        "",
        "Capability contract, version 1, stable. A switchable relay.",
    ]
    assert "- Suggested role: `relay`\n- Replaced by: `acme/power.relay2`\n" in relay
    assert "- Defined in: `score/itf/packs/acme/contracts/defs.yaml`" in relay
    assert "Long text about relays." in relay
    assert (
        "### Members\n\n- `switch(on: bool)` (required): turns it on or off\n- `read()` (optional): its state\n"
        in relay
    )
    assert "### What holding means\n\nThe relay answers read().\n" in relay
    assert "### Guarantees\n\n- switch is idempotent\n" in relay
    assert "### See also\n\n- `acme/power.on`\n" in relay
    assert "### Capability factories that fulfil it\n\n- `local.relay`\n" in relay
    assert "### Conformance checks\n\n- `relay_switches`\n" in relay
    state = _section(render.render_reference(INV), "acme/power.on")
    for absent in (
        "Suggested role",
        "Replaced by",
        "### Members",
        "### What holding",
        "### Guarantees",
        "### See also",
    ):
        assert absent not in state
    assert "- Defined in: `elsewhere/defs.yaml`" in state
    assert "### Actions that make it true\n\n- `local.power_on`\n" in state
    assert "### Conformance checks\n\nNo checks defined.\n" in state


def test_a_state_made_true_as_a_side_effect_lists_that_action_and_an_unmade_one_says_none():
    inv = {**INV, "contracts": [{**ON, "contract": "acme/power.up"}, {**ON, "contract": "acme/power.never"}]}
    text = render.render_reference(inv)
    assert "- `local.power_on`\n- `local.blind`" in _section(text, "acme/power.up")
    assert "None in the supported packs." in _section(text, "acme/power.never")


def _section(text: str, contract: str) -> str:
    start = text.index(f"## `{contract}`")
    end = text.find("\n## `", start + 1)
    return text[start : end if end != -1 else len(text)]
