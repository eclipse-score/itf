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
"""Gate 2's resolution: the steps the goals need, their bindings and their order.

The model is the one of classical (STRIPS-style) planning. A state is a name "scope:token". An action is an
operator with
    pre(a) = the states it requires,    add(a) = the states it delivers,    del(a) = the states it invalidates.
The planner is given goals G, observed states O (a probe confirmed them) and assumed states A (taken on the
caller's word), and returns an ordered list of steps.

The algorithm, in the order of `resolve_condition_to_producer`:

1. Instantiate. An action declared once for every scope (a template) becomes one instance per scope that needs
   it; the target file's relations add to an action's pre and del.
2. Select (backward chaining). Starting from G, take the action that adds each needed state, then the states it
   requires, until closed: the selected set is the smallest one closed under "requires". A needed state that no
   action adds must be in O ∪ A, else it is unreachable.
3. Bind each action's slots to roles of the target plan (gate 1), in its own scope.
4. Collapse. Instances with the same implementation and the same bound slots are one step adding the union.
5. Prune. A step whose every added state is in O ∪ A need not run, unless an active step deletes one of them;
   this is a fixed point, since re-activating a step can expose further deletions.
6. Order. Producer before consumer for every required state; a cycle is reported. Then every step that deletes
   a state is placed so that it cannot break a "producer ... consumer" link of that state (threat resolution).
7. The order is the deterministic topological order of the resulting graph.
"""

from __future__ import annotations

import dataclasses
from typing import Iterable


from ...planner import graph
from ...model.diagnostics import Diagnostic, shape_mismatches
from ...model.kinds import Kind
from ...model.plans import Edge
from ...planner.precedence import resolve_group
from ..capability.plan import TargetPlan
from .claims import AssumeClaim, GoalClaim, RelationClaim, StateContractClaim
from .plan import ActionPlan, PlannedStep


def _parse_state_ref(ref: str, default_scope: str) -> tuple[str, str]:
    if ":" in ref:
        scope, token = ref.split(":", 1)
        return scope, token
    return default_scope, ref


def resolve_condition_to_producer(
    kind: Kind,
    claims: Iterable,
    target: TargetPlan,
    *,
    precedence: tuple[str, ...] = (),
    observed_states: frozenset[str] = frozenset(),
    assumed_states: frozenset[str] = frozenset(),
) -> tuple[ActionPlan | None, tuple[Diagnostic, ...]]:
    # Gate 2 plans from the target plan, so a state can only be produced by actions whose `uses` slots the
    # target can fill; an action that needs a console on a target without one is reported, not skipped.
    # Planning works backwards from goals (what the target file wants true), pulling in only the actions needed,
    # which is why an unrelated local action costs nothing unless a target file relates a state to it.
    diags: list[Diagnostic] = []
    reported: set[tuple[str, str]] = set()

    def add_diag(code: str, subject: str, evidence: tuple = ()) -> None:
        if (code, subject) in reported:
            return
        reported.add((code, subject))
        diags.append(Diagnostic(code, subject, 2, evidence))

    if not kind.scoped:
        claims = [dataclasses.replace(c, scope="") if hasattr(c, "scope") else c for c in claims]
    state_claims = [c for c in claims if isinstance(c, StateContractClaim)]
    goal_claims = [c for c in claims if isinstance(c, GoalClaim)]
    relation_claims = [c for c in claims if isinstance(c, RelationClaim)]
    assume_claims = [c for c in claims if isinstance(c, AssumeClaim)]

    # ---- assumptions: a producer suppressed on the caller's word, never on evidence ----
    # A = scoped assumptions ("scope:token") ∪ global ones (a token, true in every scope) ∪ the request's own.
    # A state in O ∪ A needs no action; the plan later lists which of them were assumed, so it never claims
    # evidence that was not gathered.
    assume_groups = _group_by_key(assume_claims, lambda c: (c.scope, c.token))
    assumed_scoped: set[str] = set()  # "scope:token", scope != ""
    assumed_global: set[str] = set()  # bare token, scope == ""
    for key in sorted(assume_groups):
        winner, conflict = resolve_group(assume_groups[key], precedence)
        if conflict:
            add_diag("ASSUMPTION_CONFLICT", f"state:{key[1]}")
            continue
        if winner.scope:
            assumed_scoped.add(f"{winner.scope}:{winner.token}")
        else:
            assumed_global.add(winner.token)
    assumed_scoped |= set(assumed_states)  # request-level: no claim needed, just the one call

    def is_assumed(scope: str, token: str) -> bool:
        return f"{scope}:{token}" in assumed_scoped or token in assumed_global

    def satisfied_without_action(state_id: str) -> bool:
        if state_id in observed_states:
            return True
        scope, token = _parse_state_ref(state_id, "")
        return is_assumed(scope, token)

    # ---- identity, override (templates scope="", instances scope!="") ----
    # One winner per (scope, token) by precedence, as in gate 1. A claim with scope "" is a template for every
    # scope; a claim with a scope overrides the template there.
    groups = _group_by_key(state_claims, lambda c: (c.scope, c.token))
    winners: dict[tuple[str, str], StateContractClaim] = {}
    for key in sorted(groups):
        winner, conflict = resolve_group(groups[key], precedence)
        winners[key] = winner
        if conflict:
            add_diag("STATE_CONFLICT", f"state:{key[1]}")

    templates = {token: c for (scope, token), c in winners.items() if scope == ""}
    overrides = {(scope, token): c for (scope, token), c in winners.items() if scope != ""}
    known_tokens = set(templates) | {t for (_, t) in overrides}

    # ---- relation merging ----
    relations_by_token: dict[str, list[RelationClaim]] = {}
    for rc in relation_claims:
        if rc.state not in known_tokens:
            add_diag("RELATION_ORPHAN", f"state:{rc.state}")
            continue
        relations_by_token.setdefault(rc.state, []).append(rc)

    # The action that adds `token` in `scope`, looked up in this order: the scope's own claim for it, a scope
    # claim that also delivers it, the template for it, a template that also delivers it. The target file's
    # relations on that state are added to the instance: pre ∪= adds_requires, del ∪= adds_invalidates.
    def instantiate(scope: str, token: str) -> StateContractClaim | None:
        claim = overrides.get((scope, token))
        if claim is None:
            for (s, _), c in overrides.items():
                if s == scope and token in c.also_delivers:
                    claim = c
                    break
        if claim is None and token in templates:
            claim = dataclasses.replace(templates[token], scope=scope)
        if claim is None:
            for t, c in templates.items():
                if token in c.also_delivers:
                    claim = dataclasses.replace(c, scope=scope)
                    break
        if claim is None:
            return None
        if claim.scope != scope:
            claim = dataclasses.replace(claim, scope=scope)
        adds_req: frozenset[str] = frozenset()
        adds_inv: frozenset[str] = frozenset()
        for rc in relations_by_token.get(claim.token, ()):
            if rc.scope in ("", scope):
                adds_req |= rc.adds_requires
                adds_inv |= rc.adds_invalidates
        if adds_req or adds_inv:
            claim = dataclasses.replace(
                claim, requires=claim.requires | adds_req, invalidates=claim.invalidates | adds_inv
            )
        return claim

    # ---- action selection: transitive closure from goals ----
    # Backward chaining over a worklist. Invariant: every state taken from the worklist is either added by a
    # selected instance (whose requirements are then queued), or in O ∪ A, or reported unreachable. The worklist
    # only grows by states not seen yet, so the loop ends after at most |states| iterations. The result is the
    # closure of G under "requires": nothing unrelated to a goal is ever selected.
    # wanted_by records who needed each state, to explain an unreachable or unbindable one as a chain.
    instances: dict[tuple[str, str], StateContractClaim] = {}
    observed_only: set[tuple[str, str]] = set()
    goals: set[str] = set()
    todo: list[tuple[str, str]] = []
    wanted_by: dict[tuple[str, str], tuple[str, str] | None] = {}  # None: a goal
    for gc in goal_claims:
        for tok in gc.states:
            goals.add(f"{gc.scope}:{tok}")
            todo.append((gc.scope, tok))
            wanted_by[(gc.scope, tok)] = None

    seen_ok: set[tuple[str, str]] = set()
    seen_bad: set[tuple[str, str]] = set()
    while todo:
        todo.sort()
        item = todo.pop(0)
        if item in seen_ok or item in seen_bad:
            continue
        scope, token = item
        claim = instantiate(scope, token)
        if claim is None:
            if f"{scope}:{token}" in observed_states or is_assumed(scope, token):
                seen_ok.add(item)
                observed_only.add(item)
            else:
                add_diag("STATE_UNREACHABLE", f"state:{token}")
                seen_bad.add(item)
            continue
        primary_key = (scope, claim.token)
        seen_ok.add(item)
        seen_ok.add(primary_key)
        if primary_key not in instances:
            instances[primary_key] = claim
            for req in claim.requires:
                rscope, rtoken = _parse_state_ref(req, scope)
                wanted_by.setdefault((rscope, rtoken), (scope, claim.token))
                if (rscope, rtoken) not in seen_ok and (rscope, rtoken) not in seen_bad:
                    todo.append((rscope, rtoken))

    if diags:
        return None, tuple(sorted(diags, key=lambda d: (d.gate, d.code, d.subject)))

    # ---- bind `uses` against the target plan (per instance, in its own scope) ----
    # The same rule as gate 1's slots: the role the target file names, else the only role of that contract in
    # the scope, else a diagnostic. An action is planned only where the target can give it what it uses.
    resolved_uses = {key: _bind_uses(target, key, claim, wanted_by, add_diag) for key, claim in instances.items()}

    if diags:
        return None, tuple(sorted(diags, key=lambda d: (d.gate, d.code, d.subject)))

    # ---- qualify requires/invalidates/delivers; collapse by (impl, uses) ----
    # From here every state is a full "scope:token". Two instances running the same implementation on the same
    # roles would do the same thing twice, so they are one step: add, pre and del are the unions of theirs.
    def qualify(raw: frozenset[str], scope: str) -> frozenset[str]:
        out = set()
        for r in raw:
            rscope, rtoken = _parse_state_ref(r, scope)
            out.add(f"{rscope}:{rtoken}")
        return frozenset(out)

    prelim = []
    for key, claim in sorted(instances.items()):
        scope, token = key
        delivers = frozenset({f"{scope}:{token}"} | {f"{scope}:{d}" for d in claim.also_delivers})
        prelim.append(
            {
                "instance_key": key,
                "impl": claim.impl,
                "probe": claim.probe,
                "delivers": delivers,
                "requires": qualify(claim.requires, scope),
                "invalidates": qualify(claim.invalidates, scope),
                "uses": resolved_uses[key],
            }
        )

    collapse_groups: dict[tuple[str, tuple], list[dict]] = {}
    for entry in prelim:
        collapse_key = (entry["impl"], entry["uses"])
        collapse_groups.setdefault(collapse_key, []).append(entry)

    steps_by_key: dict[str, dict] = {}
    for group in collapse_groups.values():
        delivers = frozenset().union(*(e["delivers"] for e in group))
        requires = frozenset().union(*(e["requires"] for e in group))
        invalidates = frozenset().union(*(e["invalidates"] for e in group))
        key = min(delivers)
        # Each contract's probe stays evidence for exactly the states that contract delivers.
        probes = {d: e["probe"] for e in group if e["probe"] for d in e["delivers"]}
        steps_by_key[key] = {
            "key": key,
            "impl": group[0]["impl"],
            "probe": probes.get(key) or next((e["probe"] for e in group if e["probe"]), ""),
            "probes": tuple(sorted(probes.items())),
            "delivers": delivers,
            "requires": requires,
            "invalidates": invalidates,
            "uses": group[0]["uses"],
        }

    # ---- observed_states pruning (with re-delivery) ----
    def is_observed(state_id: str) -> bool:
        return satisfied_without_action(state_id)

    # Fixed point: a pruned step is only re-delivered if an *active* step destroys its state.
    # active_0 = { s : add(s) ⊄ O ∪ A };  active_{i+1} = active_i ∪ { s : add(s) ∩ del(a) ≠ ∅ for some a in active_i }.
    # The set only grows and is bounded by the steps, so it stabilises after at most |steps| rounds.
    active_keys = {k for k, s in steps_by_key.items() if not all(is_observed(x) for x in s["delivers"])}
    changed = True
    while changed:
        changed = False
        for key in sorted(steps_by_key):
            if key in active_keys:
                continue
            step = steps_by_key[key]
            if any(step["delivers"] & steps_by_key[a]["invalidates"] for a in sorted(active_keys) if a != key):
                active_keys.add(key)
                changed = True
    active = {k: v for k, v in steps_by_key.items() if k in active_keys}

    # ---- edge derivation ----
    # A causal edge a -> b for every state s with s ∈ add(a) ∩ pre(b): the producer runs before the consumer.
    # A cycle here means steps that each need the other first; no order exists and it is reported.
    edges: list[Edge] = []
    edge_set: set[tuple[str, str]] = set()

    def add_edge(before: str, after: str, reason: str, state: str) -> None:
        edges.append(Edge(before=before, after=after, reason=reason, state=state))
        edge_set.add((before, after))

    keys_sorted = sorted(active)
    consumers: dict[str, list[str]] = {}
    for b in keys_sorted:
        for s in active[b]["requires"]:
            consumers.setdefault(s, []).append(b)
    for a in keys_sorted:
        # same order as iterating every b, then every shared state, both sorted
        for b, s in sorted((b, s) for s in active[a]["delivers"] for b in consumers.get(s, ()) if b != a):
            add_edge(a, b, "delivers-requires", s)

    cyc = graph.find_cycle(keys_sorted, frozenset(edge_set))
    if cyc:
        add_diag("STATE_CYCLE", cyc[0])
        return None, tuple(sorted(diags, key=lambda d: (d.gate, d.code, d.subject)))

    if "destroys" in kind.roles:
        conflict = _protect_causal_links(active, keys_sorted, goals, edge_set, add_edge)
        if conflict:
            add_diag("ORDER_AMBIGUOUS", min(conflict), evidence=(("between", " , ".join(sorted(conflict))),))
            return None, tuple(sorted(diags, key=lambda d: (d.gate, d.code, d.subject)))

    if diags:
        return None, tuple(sorted(diags, key=lambda d: (d.gate, d.code, d.subject)))

    order = graph.toposort_kahn(keys_sorted, frozenset(edge_set))

    steps = tuple(
        PlannedStep(
            key=active[k]["key"],
            impl=active[k]["impl"],
            probe=active[k]["probe"],
            delivers=tuple(sorted(active[k]["delivers"])),
            requires=tuple(sorted(active[k]["requires"])),
            invalidates=tuple(sorted(active[k]["invalidates"])),
            uses=active[k]["uses"],
            probes=tuple((d, ref) for d, ref in active[k].get("probes", ()) if d in active[k]["delivers"]),
        )
        for k in order
    )
    unprobed = tuple(sorted(k for k in order if active[k]["probe"] == ""))

    # Of every state this resolution touched, the ones taken on the caller's word rather than
    # (the assumed list: touched ∩ A, minus what an active step delivers for real)
    # observed or executed — visible so a plan never implies evidence that was never gathered.
    # A state re-delivered because an active step destroys it ran for real: it is not an assumption.
    touched_ids = {f"{s}:{t}" for s, t in seen_ok}
    delivered_by_active = frozenset().union(*(s["delivers"] for s in active.values())) if active else frozenset()
    assumed = tuple(
        sorted(x for x in touched_ids if is_assumed(*_parse_state_ref(x, "")) and x not in delivered_by_active)
    )

    plan = ActionPlan(
        goals=tuple(sorted(goals)),
        observed_at_plan_time=tuple(sorted(observed_states)),
        steps=steps,
        edges=tuple(edges),
        unprobed=unprobed,
        assumed=assumed,
    )
    return plan, ()


# Planner ordering needs more than dependency edges: an action that invalidates a state (a restart drops the
# connection) must not run between the action that delivers it and the step that relies on it. This is the
# classic STRIPS threat-resolution step, kept deterministic so plans are stable across runs.
def _protect_causal_links(active, keys, goals, edge_set, add_edge) -> tuple[str, str] | None:
    """Order every destroyer so no causal link it threatens is broken (STRIPS threat resolution).

    A link is (producer, state, consumer): the producer delivers the state and the consumer needs it
    to still hold — a step that requires it, or the end of the plan when it is a goal. A destroyer D
    of that state must run before the producer or after the consumer. Forced choices are applied to
    a fixed point; a free choice defaults to destroy-then-produce. Returns the conflicting pair when
    no consistent order exists.
    """
    # producer(s): the step that adds s (the smallest step key when several do).
    producer: dict[str, str] = {}
    for k in keys:
        for s in sorted(active[k]["delivers"]):
            producer.setdefault(s, k)

    # Causal links (p, s, c): p adds s and c relies on it until it runs. c is None for a goal: s must still hold
    # at the end of the plan. p is None for a state nothing in the plan adds (observed or assumed).
    links: list[tuple[str | None, str, str | None]] = []
    for c in keys:
        for s in sorted(active[c]["requires"]):
            links.append((producer.get(s), s, c))
    for g in sorted(goals):
        if g in producer:
            links.append((producer[g], g, None))

    destroyers: dict[str, list[str]] = {}
    for d in keys:
        for s in active[d]["invalidates"]:
            destroyers.setdefault(s, []).append(d)
    # A threat is a step d with s ∈ del(d) for a link (p, s, c), d ∉ {p, c}: if d ran between p and c, c would
    # find s false. It is resolved by ordering d before p ("demotion") or after c ("promotion").
    open_threats: list[tuple[str, str | None, str | None, str]] = []
    for p, s, c in links:
        for d in destroyers.get(s, ()):
            if d not in (p, c):
                open_threats.append((d, p, c, s))

    # Reachability kept exact as edges are added, instead of recomputed after every decision.
    # succ[x] = every step that must run after x (the transitive closure of the edges). Adding a -> b makes b
    # and succ[b] follow a, and follow every x that a already follows: succ[x] ∪= {b} ∪ succ[b] for x = a and
    # every x with a ∈ succ[x]. So "d is already ordered before p" is the O(1) test p ∈ succ[d].
    succ: dict[str, set[str]] = {k: set() for k in keys}
    for a, b in graph.reachable_pairs(keys, frozenset(edge_set)):
        succ[a].add(b)

    def connect(a: str, b: str, s: str) -> None:
        add_edge(a, b, "invalidates", s)
        targets = {b} | succ[b]
        for x in keys:
            if x == a or a in succ[x]:
                succ[x] |= targets

    # For each threat (d, p, c, s):
    #   already safe   p ∈ succ[d] (d runs before p) or d ∈ succ[c] (d runs after c): nothing to add;
    #   before_ok      d may still go before p: p exists, and d does not already follow p;
    #   after_ok       d may still go after c: c exists, and c does not already follow d;
    #   neither        no order keeps the link: ORDER_AMBIGUOUS, naming the pair;
    #   exactly one    the choice is forced: add it, and rescan, since the new edge may force or settle others;
    #   both           undecided for now.
    # When only undecided threats are left, the first (in sorted order) is resolved by demotion, d before p,
    # and the scan continues. Every pass either adds an edge or removes threats, so the loop ends.
    while open_threats:
        undecided = []
        progressed = False
        for d, p, c, s in open_threats:
            before_ok = p is not None and d != p and d not in succ[p]
            after_ok = c is not None and c not in succ[d]
            if (p is not None and p in succ[d]) or (c is not None and d in succ[c]):
                continue
            if not before_ok and not after_ok:
                return (d, c if c is not None else p)
            if before_ok != after_ok:
                if before_ok:
                    connect(d, p, s)
                else:
                    connect(c, d, s)
                progressed = True
                break
            undecided.append((d, p, c, s))
        if progressed:
            continue
        if not undecided:
            return None
        d, p, c, s = undecided[0]
        connect(d, p, s)
        open_threats = undecided[1:]
    return None


def _group_by_key(claims, key_fn):
    groups: dict = {}
    for c in claims:
        groups.setdefault(key_fn(c), []).append(c)
    return groups


def _unsatisfied_evidence(target: TargetPlan, scope: str, token: str, claim, need, wanted_by) -> tuple:
    """What a reader needs to fix a missing `uses`: what was needed, by whom, why, and where it exists."""
    chain, key = [], (scope, token)
    while wanted_by.get(key) is not None and len(chain) < len(wanted_by):
        key = wanted_by[key]
        chain.append(f"{key[0]}:{key[1]}")
    elsewhere = sorted(n.ref for n in target.nodes if n.contract == need.contract and n.scope != scope)
    return tuple(
        sorted(
            {
                "action": claim.impl,
                "contract": need.contract,
                "elsewhere": ", ".join(elsewhere),
                "required_by": " <- ".join(chain),
                "scope": scope,
                "slot": need.slot,
            }.items()
        )
    )


def _bind_uses(target: TargetPlan, key: tuple[str, str], claim, wanted_by, add_diag) -> tuple:
    """((slot, role ref), ...) for the slots of one action instance; a slot that cannot be bound is reported."""
    scope, token = key
    pairs = []
    for need in sorted(claim.uses, key=lambda n: n.slot):
        ref, code, evidence = _bind_use(target, scope, need, dict(claim.bind).get(need.slot))
        subject = f"{scope}:{token}#{need.slot}"
        if ref is None:
            if code == "USES_UNSATISFIED":
                evidence = _unsatisfied_evidence(target, scope, token, claim, need, wanted_by)
            add_diag(code, subject, evidence=evidence)
            continue
        for d in shape_mismatches(subject, target.node(ref).gives, need.expected, 2):
            add_diag(d.code, d.subject, d.evidence)
        pairs.append((need.slot, ref))
    return tuple(sorted(pairs))


def _bind_use(target: TargetPlan, scope: str, need, role: str | None) -> tuple[str | None, str, tuple]:
    """How an action's slot is filled, in this order: the role the target file named (`role`), else the one
    role of the slot's contract in the scope, else an error. Returns (ref, "", ()) on success, else
    (None, diagnostic code, evidence)."""
    if role is not None:
        return _explicit_use(target, scope, need, role)
    candidates = use_candidates(target, scope, need.contract)
    if len(candidates) == 1:
        return candidates[0], "", ()
    if not candidates:
        return None, "USES_UNSATISFIED", ()
    return None, "USES_AMBIGUOUS", tuple(("candidate", c) for c in candidates)


def _explicit_use(target: TargetPlan, scope: str, need, role: str) -> tuple[str | None, str, tuple]:
    try:
        ref = target.resolve(f"{scope}.{role}")
    except KeyError:
        return None, "USES_BIND_INVALID", (("reason", "no such role in the scope"), ("role", role))
    if target.node(ref).contract != need.contract:
        reason = f"it is a {target.node(ref).contract!r}, the slot needs a {need.contract!r}"
        return None, "USES_BIND_INVALID", (("reason", reason), ("role", role))
    return ref, "", ()


def use_candidates(target: TargetPlan, scope: str, contract: str) -> tuple[str, ...]:
    """The roles of `scope` (shared ones included) that fulfil `contract`, as plan refs, sorted."""
    return target.refs_of(scope, contract)
