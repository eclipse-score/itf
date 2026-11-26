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
"""One template per OCTO diagnostic code, worded for a target file: roles, factory labels, contract names.

`CODES` is the closed set (`score.itf.core.octo.CODES`: core codes plus every standard relation's); a test
enumerates it against `TEMPLATES` so a code with no template fails the build.
"""

from __future__ import annotations

from ..octo import Diagnostic
from .scopes import ROOT, display


def _evidence(d: Diagnostic) -> dict:
    return dict(d.evidence)


class Context:
    """What the templates may look up: the catalog (who offers what) and each scope's roles."""

    def __init__(self, catalog=None, roles=None):
        self.catalog = catalog
        self.roles = roles or {}

    def factory_of(self, ref: str) -> str | None:
        scope, _, name = ref.rpartition(".")
        return self.roles.get(scope, {}).get(name)

    def need(self, subject: str):
        """(role, slot, contract, candidate labels) of a `<scope>.<role>#<slot>` subject, when known."""
        ref, _, slot = subject.partition("#")
        label = self.factory_of(ref)
        factory = self.catalog.factories.get(label) if (self.catalog and label) else None
        if factory is None:
            return None
        contract = next((n.contract for n in factory.needs if n.slot == slot), None)
        if contract is None:
            return None
        return ref.rpartition(".")[2], label, slot, contract, self.catalog.offering(contract)


def _t(summary: str, fix: str):
    def render_one(d: Diagnostic, ctx: Context) -> str:
        ev = _evidence(d)
        return f"{d.subject}: {summary.format(d=d, ev=ev)}\n  Fix: {fix.format(d=d, ev=ev)}"

    return render_one


def _slot_missing(d: Diagnostic, ctx: Context) -> str:
    found = ctx.need(d.subject)
    if found is None:
        return (
            f"{d.subject}: a slot has no capability in this scope, and nothing outside the target file is added\n"
            "  Fix: list a capability that fulfils it under `capabilities:`, or point `bind:` at one"
        )
    role, label, slot, contract, offering = found
    lines = [
        f"{d.subject}: {role} ({label}) needs a {contract!r} for its slot {slot!r}, and the target file lists none",
    ]
    if offering:
        lines.append(f"  Candidates: {', '.join(offering)}")
        lines.append(f"  Fix: list one, for example\n    capabilities:\n      {slot}: {offering[0]}")
    else:
        lines.append("  No loaded pack has a capability factory for it.")
        lines.append(f"  Fix: list a factory that fulfils {contract!r} (from a pack, or your own @capability)")
    return "\n".join(lines)


def _slot_ambiguous(d: Diagnostic, ctx: Context) -> str:
    candidates = [display(v).rpartition(".")[2] for k, v in d.evidence if k == "candidate"]
    slot = d.subject.partition("#")[2]
    role = display(d.subject.partition("#")[0])
    return (
        f"{d.subject}: more than one role could fill slot {slot!r} of {role}: {', '.join(candidates)}\n"
        f"  Fix: say which with `bind:`\n    {role}:\n      bind:\n        {slot}: {candidates[0] if candidates else '<role>'}"
    )


def _uses_unsatisfied(d: Diagnostic, ctx: Context) -> str:
    ev = _evidence(d)
    if "contract" not in ev:
        return (
            f"{d.subject}: the action at '{d.subject}' needs a capability the target plan does not have\n"
            "  Fix: list a capability that fulfils it under `capabilities:`"
        )
    scope, slot, contract = ev["scope"], ev["slot"], ev["contract"]
    state = d.subject.split("#", 1)[0]
    where = "the root scope" if scope == ROOT else f"scope '{scope}'"
    why = f"{state} is required by {ev['required_by']} (a goal)" if ev.get("required_by") else f"{state} is a goal"
    offering = ctx.catalog.offering(contract) if ctx.catalog else ()
    lines = [
        f"{d.subject}: {where} has no {contract!r} capability, and reaching {state} needs one",
        f"  Needed by: {ev['action']}, slot '{slot}'",
        f"  Why: {why}",
    ]
    if ev.get("elsewhere"):
        lines.append(f"  Exists in: {ev['elsewhere']}")
        lines.append(
            f"  Fix: share it into this scope (`share:` the root role), or list one here; or drop {state} from the goals"
        )
    else:
        if offering:
            lines.append(f"  Candidates: {', '.join(offering)}")
        lines.append(
            f"  Fix: list a capability that fulfils {contract!r} in this scope; or drop {state} from the goals"
        )
    return "\n".join(lines)


def _uses_ambiguous(d: Diagnostic, ctx: Context) -> str:
    candidates = [display(v).rpartition(".")[2] for k, v in d.evidence if k == "candidate"]
    state, _, slot = d.subject.partition("#")
    return (
        f"{d.subject}: more than one role could fill the action's slot {slot!r} for {state}: {', '.join(candidates)}\n"
        f"  Fix: say which with `actions:`\n    actions:\n      <action label>:\n        bind:\n"
        f"          {slot}: {candidates[0] if candidates else '<role>'}"
    )


TEMPLATES = {
    "CONTRACT_CONFLICT": _t(
        "two contract declarations claim '{d.subject}' at the same precedence",
        "declare it once",
    ),
    "PROVIDER_CONFLICT": _t(
        "two capability factories have the label '{d.subject}'",
        "give one a different label (`@capability(..., label=...)`); labels are unique per pack",
    ),
    "NAME_COLLISION": _t(
        "two entries collide on '{d.subject}' with no precedence to break the tie",
        "a role is declared once; merge the entries or rename one role",
    ),
    "ALIAS_UNRESOLVED": _t(
        "the shared role '{d.subject}' points at a role that does not exist",
        "`share:` names roles of the root; check the spelling under the root's `capabilities:`",
    ),
    "ALIAS_CYCLE": _t(
        "the shared role '{d.subject}' is part of a cycle",
        "a shared role must eventually be a role of the root",
    ),
    "REBIND_ORPHAN": _t(
        "'{d.subject}' binds something that is not a role or a slot of its factory",
        "check the role and the slot names under `bind:`",
    ),
    "PROVIDER_UNKNOWN": _t(
        "the factory '{ev[provider]}' is not published by any loaded pack",
        "check the label (<pack>.<factory>) and that the pack is installed",
    ),
    "PROVIDER_CONTRACT_MISMATCH": _t(
        "the factory of '{d.subject}' fulfils another contract than the role declares",
        "pick a factory for the contract the role needs",
    ),
    "NO_PROVIDER": _t(
        "no capability factory fulfils the contract needed at '{d.subject}'",
        "list a factory that does, under `capabilities:`",
    ),
    "PROVIDER_AMBIGUOUS": _t(
        "more than one capability factory fulfils the contract needed at '{d.subject}'",
        "list the one you want under `capabilities:`; nothing is chosen for you",
    ),
    "BINDING_UNKNOWN": _t(
        "`bind:` at '{d.subject}' names a role the target does not have",
        "bind the slot to a role listed under `capabilities:`",
    ),
    "BINDING_CONTRACT_MISMATCH": _t(
        "the role bound to '{d.subject}' does not fulfil the slot's contract",
        "bind the slot to a role whose factory fulfils the contract the slot names",
    ),
    "SLOT_AMBIGUOUS": _slot_ambiguous,
    "SLOT_UNSATISFIED": _slot_missing,
    "CYCLE": _t(
        "a construction cycle passes through '{d.subject}'",
        "break the cycle: one of these bindings must point elsewhere",
    ),
    "STATE_CONFLICT": _t(
        "two actions make the state '{d.subject}' true at the same precedence",
        "choose one: `- state: {d.subject}` with `by: <action label>` under `goals:`",
    ),
    "RELATION_ORPHAN": _t(
        "a relation amends the state '{d.subject}', which no action makes true",
        "check the state name in the action's `after=`/`breaks=`",
    ),
    "USES_UNSATISFIED": _uses_unsatisfied,
    "USES_AMBIGUOUS": _uses_ambiguous,
    "USES_BIND_INVALID": _t(
        "`actions:` binds a slot at '{d.subject}' to the role '{ev[role]}', but {ev[reason]}",
        "bind the slot to a role of the scope whose factory fulfils the slot's contract",
    ),
    "STATE_UNREACHABLE": _t(
        "the state '{d.subject}' cannot be reached: no action of the listed packs makes it true and it was not observed",
        "list a capability factory of a pack whose action makes it true, or `assume:` it with an owner and a reason",
    ),
    "STATE_CYCLE": _t(
        "a temporal cycle passes through '{d.subject}'",
        "one of the actions' `after=`/`breaks=` must change",
    ),
    "ORDER_AMBIGUOUS": _t(
        "two actions mutually break each other's state near '{d.subject}' with no derivable order",
        "change an action's `after=` so one must run first",
    ),
    "ASSUMPTION_CONFLICT": _t(
        "two `assume:` entries for '{d.subject}' disagree",
        "state it once, with one owner and reason",
    ),
    "SHAPE_MISSING_MEMBER": _t(
        "the seam at '{d.subject}' is missing member(s): {ev}",
        "pick a factory that offers them, or lower what the consumer's slot annotation expects",
    ),
    "SHAPE_SIGNATURE_DRIFT": _t(
        "the seam at '{d.subject}' has a signature mismatch: {ev}",
        "align the factory's return type with the consumer's slot annotation",
    ),
    "SHAPE_PROTOCOL_MISSING": _t(
        "the seam at '{d.subject}' does not satisfy the expected protocol: {ev}",
        "have the factory's return type declare the protocol, or lower the consumer's annotation",
    ),
    "SHAPE_UNDECLARED": _t(
        "the seam at '{d.subject}' declares no shape: it expects no member of what it binds to",
        "give the slot's annotation the members the consumer relies on",
    ),
    "CLAIM_WRONG_GATE": _t(
        "a claim for '{d.subject}' was offered to the wrong gate",
        "this is a defect in ITF's compiler, not in the target file; report it",
    ),
    "UNKNOWN_KIND": _t(
        "a '{d.subject}' was offered to the planner, but no registered contract kind owns that claim type",
        "this is a defect in ITF's compiler, not in the target file; report it",
    ),
    "RELATION_FAILED": _t(
        "the planner for '{d.subject}' failed instead of answering: {ev}",
        "this is a defect in that kind's relation, not in your target file; report it with the evidence above",
    ),
}


def render(diagnostics, *, gate: int, phase: str, catalog=None, roles=None) -> str:
    ctx = Context(catalog, roles)
    lines = [f"Gate {gate} \u00b7 {phase}"]
    for d in diagnostics:
        template = TEMPLATES.get(d.code)
        if template is None:
            lines.append(f"{d.subject}: {d.code} (no template)")
        else:
            lines.append(template(d, ctx))
    return display("\n".join(lines))
