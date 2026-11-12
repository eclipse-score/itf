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
"""Renderers of the contract inventory (`inventory.inventory`): text, JSON, Mermaid, one HTML page and the
Markdown reference. All output is deterministic, so a checked-in copy can be compared with a fresh one."""

from __future__ import annotations

import html
import json
import re

FORMATS = ("text", "json", "mermaid", "html")


def _members(items) -> str:
    return ", ".join(items) if items else "-"


def _at(contract: str, major) -> str:
    return f"{contract}@{major}" if major else contract


# ---- text -----------------------------------------------------------------------------------------------------


def _contract_text(contract: dict) -> list[str]:
    definition = contract["definition"]
    head = f"{contract['contract']}  [{contract['kind']}]"
    head += f"  defined v{definition['version']} ({definition['stability']})" if definition else "  not defined"
    lines = [head]
    for item in contract["offered_by"]:
        lines.append(f"  offered by {_at(item['label'], item['major'])}: {_members(item['shape'])}")
    for item in contract["needed_by"]:
        expects = f": expects {_members(item['expects'])}" if item["expects"] else ""
        major = f" @{item['major']}" if item["major"] else ""
        lines.append(f"  needed by  {item['label']} ({item['slot']}){major}{expects}")
    for item in contract["tests"]:
        major = f" @{item['major']}" if item.get("major") is not None else ""
        lines.append(
            f"  test       {item['test'] or item['role']} (role {item['role']}){major}: {_members(item['shape'])}"
        )
    lines += [f"  DISAGREES  {item['kind']}: {item['message']}" for item in contract["disagreements"]]
    return lines + [""]


def render_text(inv: dict) -> str:
    lines = []
    for contract in inv["contracts"]:
        lines += _contract_text(contract)
    disagreements = sum(len(c["disagreements"]) for c in inv["contracts"])
    undefined = sum(1 for c in inv["contracts"] if c["definition"] is None)
    lines += [f"{len(inv['contracts'])} contracts, {undefined} without a definition, {disagreements} disagreements"]
    lines += [f"error: {e}" for e in inv["errors"]]
    return "\n".join(lines)


def render_json(inv: dict) -> str:
    return json.dumps(inv, indent=2, sort_keys=True)


# ---- mermaid --------------------------------------------------------------------------------------------------


def _id(text: str) -> str:
    return re.sub(r"\W", "_", text)


def render_mermaid(inv: dict) -> str:
    """Factories offer a contract (solid edge) and need contracts through slots (dashed edge)."""
    lines = ["flowchart LR"]
    for contract in inv["contracts"]:
        shape = "([{}])" if contract["kind"] == "state" else "[[{}]]"
        lines.append(f"  c_{_id(contract['contract'])}{shape.format(chr(34) + contract['contract'] + chr(34))}")
    for contract in inv["contracts"]:
        cid = f"c_{_id(contract['contract'])}"
        for item in contract["offered_by"]:
            lines.append(f'  p_{_id(item["label"])}["{item["label"]}"] --> {cid}')
        for item in contract["needed_by"]:
            lines.append(f'  {cid} -.->|{item["slot"]}| p_{_id(item["label"])}["{item["label"]}"]')
    return "\n".join(lines)


# ---- html -----------------------------------------------------------------------------------------------------

STYLE = """
:root{--bg:#f6f7f9;--panel:#fff;--ink:#1d2433;--muted:#5d6779;--line:#e1e5ec;--cap:#2563eb;--state:#0f8a5f;
--bad:#b42318;--code:#f1f3f7}
@media(prefers-color-scheme:dark){:root{--bg:#10141b;--panel:#171c26;--ink:#e6e9ef;--muted:#9aa4b5;--line:#2a3140;
--cap:#7aa2ff;--state:#4cc9a0;--bad:#ff8b7e;--code:#1f2633}}
:root[data-theme=light]{--bg:#f6f7f9;--panel:#fff;--ink:#1d2433;--muted:#5d6779;--line:#e1e5ec;--cap:#2563eb;
--state:#0f8a5f;--bad:#b42318;--code:#f1f3f7}
:root[data-theme=dark]{--bg:#10141b;--panel:#171c26;--ink:#e6e9ef;--muted:#9aa4b5;--line:#2a3140;--cap:#7aa2ff;
--state:#4cc9a0;--bad:#ff8b7e;--code:#1f2633}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}
header{padding:16px 16px 8px;max-width:1100px;margin:0 auto}h1{margin:0;font-size:22px}
.muted{color:var(--muted)}main{max-width:1100px;margin:0 auto;padding:0 16px 48px}
nav a{margin-right:14px;color:var(--cap)}input{width:100%;padding:8px 10px;margin:10px 0;border:1px solid var(--line);
border-radius:8px;background:var(--panel);color:var(--ink)}
section>h2{margin:28px 0 8px}.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:10px 14px;margin:8px 0}.card h3{margin:0 0 4px;font-size:16px}
code,.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.88em;background:var(--code);
padding:0 4px;border-radius:4px}.cap{color:var(--cap)}.state{color:var(--state)}.bad{color:var(--bad)}
ul{margin:4px 0;padding-left:20px}.hidden{display:none}
"""

SCRIPT = """
const box=document.getElementById('q');
box.addEventListener('input',()=>{const q=box.value.toLowerCase();
document.querySelectorAll('.card').forEach(c=>c.classList.toggle('hidden',q&&!c.textContent.toLowerCase().includes(q)));});
"""


def _e(text) -> str:
    return html.escape(str(text))


def _list(items, empty="none") -> str:
    items = list(items)
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>" if items else f'<p class="muted">{empty}</p>'


def _card_head(c: dict) -> str:
    d = c["definition"]
    css = "state" if c["kind"] == "state" else "cap"
    defined = f", v{d['version']}, {_e(d['stability'])}</span></h3>" if d else ", not defined</span></h3>"
    return (
        f'<div class="card" id="c-{_e(c["contract"])}"><h3><span class="{css}">{_e(c["contract"])}</span> '
        f'<span class="muted">{_e(c["kind"])}{defined}'
    )


def _definition_html(d: dict) -> list[str]:
    parts = [f"<p>{_e(d['summary'])}</p>"]
    if d["role"]:
        parts.append(f'<p class="muted">suggested role: <code>{_e(d["role"])}</code></p>')
    if d["members"]:
        parts.append("<p>Members</p>" + _list(_member_item(m) for m in d["members"]))
    if d["guarantees"]:
        parts.append("<p>Guarantees</p>" + _list(_e(g) for g in d["guarantees"]))
    return parts


def _member_item(m: dict) -> str:
    return (
        f"<code>{_e(m['name'])}{_e(m['signature'])}</code> ({'required' if m['required'] else 'optional'}): "
        f"{_e(m['semantics'])}"
    )


def _offered_html(c: dict) -> str:
    items = (f"<code>{_e(_at(i['label'], i['major']))}</code> {_e(_members(i['shape']))}" for i in c["offered_by"])
    return "<p>Offered by</p>" + _list(items, empty="nobody")


def _needed_html(c: dict) -> str:
    return "<p>Needed by</p>" + _list(
        f"<code>{_e(i['label'])}</code> slot <code>{_e(i['slot'])}</code> expects {_e(_members(i['expects']))}"
        + (f"; requires {_e(_at(c['contract'], i['major']))}" if i["major"] is not None else "")
        for i in c["needed_by"]
    )


def _tests_html(c: dict) -> str:
    items = []
    for item in c["tests"]:
        major = f"@{item['major']} " if item.get("major") is not None else ""
        items.append(
            f"{_e(item['test'] or item['role'])}: role <code>{_e(item['role'])}</code> "
            f"{_e(major)}{_e(_members(item['shape']))}"
        )
    return "<p>Tests</p>" + _list(items)


def _contract_card(c: dict) -> str:
    d = c["definition"]
    parts = [_card_head(c)] + (_definition_html(d) if d else []) + [_offered_html(c), _needed_html(c)]
    if c["tests"]:
        parts.append(_tests_html(c))
    if c["checks"]:
        parts.append("<p>Conformance checks</p>" + _list(f"<code>{_e(n)}</code>" for n in c["checks"]))
    if c["disagreements"]:
        parts.append('<p class="bad">Disagreements</p>' + _list(_e(i["message"]) for i in c["disagreements"]))
    return "".join(parts) + "</div>"


def _factory_card(f: dict) -> str:
    needs = [
        f"slot <code>{_e(n['slot'])}</code>: {_e(_at(n['contract'], n['major']))} expects {_e(_members(n['expects']))}"
        for n in f["needs"]
    ]
    config = [
        f"<code>{_e(c['name'])}</code> {_e(c['type'])}"
        + (" required" if c["required"] else f" default {_e(c.get('default', ''))}" if not c["sensitive"] else "")
        + (" secret" if c["sensitive"] else "")
        for c in f["config"]
    ]
    return (
        f'<div class="card" id="f-{_e(f["label"])}"><h3><code>{_e(f["label"])}</code> '
        f'<span class="muted">offers <span class="cap">{_e(_at(f["contract"], f["major"]))}</span></span></h3>'
        f"<p>shape: {_e(_members(f['shape']))}</p><p>Needs</p>{_list(needs)}<p>Settings</p>{_list(config)}"
        f'<p class="muted">observed by a later process: {_e(f["observes"])}</p></div>'
    )


def _action_card(a: dict) -> str:
    uses = _list(f"slot <code>{_e(u['slot'])}</code>: {_e(_at(u['contract'], u.get('major')))}" for u in a["uses"])
    return (
        f'<div class="card" id="a-{_e(a["label"])}"><h3><code>{_e(a["label"])}</code> '
        f'<span class="muted">makes <span class="state">{_e(a["state"])}</span> true</span></h3>'
        f"<p>after: {_e(_members(a['after']))}; breaks: {_e(_members(a['breaks']))}; also: {_e(_members(a['also']))}"
        f"; probe: {'yes (skippable when it holds)' if a['probe'] else 'no (always runs)'}</p>"
        f"<p>Uses</p>{uses}</div>"
    )


def _pack_card(p: dict) -> str:
    return (
        f'<div class="card" id="p-{_e(p["name"])}"><h3><code>{_e(p["name"])}</code> '
        f'<span class="muted">{_e(p["version"])}</span></h3><p>{_e(p["summary"])}</p>'
        f"<p>Factories: {_e(_members(p['factories']))}</p><p>Actions: {_e(_members(p['actions']))}</p>"
        f"<p>Prerequisites</p>{_list(_e(i) for i in p['prerequisites'])}</div>"
    )


def render_html(inv: dict, title: str = "ITF contract map") -> str:
    contracts = inv["contracts"]
    disagreements = sum(len(c["disagreements"]) for c in contracts)
    body = [
        f"<header><h1>{_e(title)}</h1>",
        f'<p class="muted">{len(inv["packs"])} packs, {len(contracts)} contracts, {len(inv["factories"])} capability '
        f"factories, {len(inv['actions'])} actions, {disagreements} disagreements. Generated by "
        f"<code>itf contracts map --format html</code>.</p>",
        '<nav><a href="#contracts">Contracts</a><a href="#factories">Capability factories</a>'
        '<a href="#actions">Actions</a><a href="#packs">Packs</a></nav>',
        '<input id="q" type="search" placeholder="Filter by name, contract, member, pack" autocomplete="off"></header>',
        "<main>",
    ]
    for error in inv["errors"]:
        body.append(f'<div class="card bad">{_e(error)}</div>')
    for name, heading, cards in (
        ("contracts", "Contracts", [_contract_card(c) for c in contracts]),
        ("factories", "Capability factories", [_factory_card(f) for f in inv["factories"]]),
        ("actions", "Actions", [_action_card(a) for a in inv["actions"]]),
        ("packs", "Packs", [_pack_card(p) for p in inv["packs"]]),
    ):
        body.append(f'<section id="{name}"><h2>{heading}</h2>{"".join(cards)}</section>')
    body.append("</main>")
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_e(title)}</title><style>{STYLE}</style></head><body>{''.join(body)}"
        f"<script>{SCRIPT}</script></body></html>\n"
    )


def render(inv: dict, fmt: str) -> str:
    if fmt not in FORMATS:
        raise ValueError(f"format is one of {', '.join(FORMATS)}, not {fmt!r}")
    return {"text": render_text, "json": render_json, "mermaid": render_mermaid, "html": render_html}[fmt](inv)


# ---- reference ------------------------------------------------------------------------------------------------

REFERENCE_HEADER = """<!--
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
"""

REFERENCE_INTRO = """# Contracts

This page is generated from the supported contract definitions (`score/itf/packs/*/contracts/*.yaml`) and the
packs' code. Do not edit it by hand: run
`bazel run //score/itf/cli:itf -- contracts reference --output docs/reference/contracts.md`.

ITF knows no contracts: a contract is a name two parts agree on. These are the ones the ITF team maintains for
its own packs, as a supported set and not as a standard. A **capability contract** is fulfilled by a capability
factory (`@capability`) and used in a test through a role; a **state contract** is made true by an action
(`@state`) and listed under `goals:`. A definition adds meaning, a version, members, a suggested role, a
stability and a conformance suite. `itf contracts map` shows every contract in use, with its disagreements.
"""


def _definition_lines(d: dict) -> list[str]:
    """The optional parts of a definition, each only when it has content."""
    lines = []
    if d["members"]:
        lines += ["### Members", ""] + [_member_line(m) for m in d["members"]] + [""]
    if d["probe"]:
        lines += ["### What holding means", "", d["probe"], ""]
    if d["guarantees"]:
        lines += ["### Guarantees", ""] + [f"- {g}" for g in d["guarantees"]] + [""]
    if d["see_also"]:
        lines += ["### See also", ""] + [f"- `{s}`" for s in d["see_also"]] + [""]
    return lines


def _member_line(m: dict) -> str:
    return f"- `{m['name']}{m['signature']}` ({'required' if m['required'] else 'optional'}): {m['semantics']}"


def _makers(c: dict, inv: dict) -> list[str]:
    """Who makes the contract true: the actions for a state, the capability factories for a capability."""
    if c["kind"] == "state":
        labels = [a["label"] for a in inv["actions"] if c["contract"] in (a["state"], *a["also"])]
        heading = "### Actions that make it true"
    else:
        labels = [i["label"] for i in c["offered_by"]]
        heading = "### Capability factories that fulfil it"
    return [heading, ""] + ([f"- `{label}`" for label in labels] if labels else ["None in the supported packs."])


def _section(c: dict, inv: dict) -> list[str]:
    d = c["definition"]
    lines = [
        f"## `{c['contract']}`",
        "",
        f"{c['kind'].capitalize()} contract, version {d['version']}, {d['stability']}. {d['summary']}",
        "",
    ]
    lines += [f"- Suggested role: `{d['role']}`"] if d["role"] else []
    lines += [f"- Replaced by: `{d['replaced_by']}`"] if d["replaced_by"] else []
    lines += [f"- Defined in: `{_relative(d['source'])}`", "", d["description"], ""]
    lines += _definition_lines(d) + _makers(c, inv) + ["", "### Conformance checks", ""]
    lines += [f"- `{n}`" for n in c["checks"]] if c["checks"] else ["No checks defined."]
    return lines + [""]


def _relative(source: str) -> str:
    match = re.search(r"(score/itf/(?:packs|contracts)/\S+): (\S+)$", source)
    return f"{match.group(1)}/{match.group(2)}" if match else source


def render_reference(inv: dict) -> str:
    defined = [c for c in inv["contracts"] if c["definition"] is not None]
    lines = [REFERENCE_INTRO, "## Index", "", "| Contract | Kind | Stability | Summary |", "|---|---|---|---|"]
    for c in defined:
        d = c["definition"]
        lines.append(f"| `{c['contract']}` | {c['kind']} | {d['stability']} | {d['summary']} |")
    lines.append("")
    for c in defined:
        lines += _section(c, inv)
    return REFERENCE_HEADER + "\n".join(lines).rstrip() + "\n"
