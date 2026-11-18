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
"""Gate 1's resolution: one node per name, its provider, its bindings, its shapes, its order.

The algorithm, in the order of `resolve_contract_to_node`:

1.1  Index the vocabulary: contracts and providers by name; duplicates that differ are conflicts.
1.2  Decide each node (scope, name): the highest-ranked claim wins. Resolve aliases (a second name for a node)
     by following them to a real node, refusing cycles. Build, per scope, the table of visible names and the
     index I(scope, contract) = the nodes of that scope declaring the contract.
1.3  Choose each node's provider: the one it names, else the only provider of its contract, else an error.
1.4  Bind each slot of each provider: the explicit bind, else the only candidate |I(scope, contract)| = 1,
     else ambiguous (> 1) or unsatisfied (0). Every binding is a seam whose shapes are compared.
1.6  The bindings form the construction graph (dependency before dependent); refuse a cycle, then order it
     topologically.

Every step adds diagnostics instead of stopping, so one run reports every problem; the plan is returned only
when there are none. Every iteration is over sorted keys, so the same claims always give the same plan.
"""

from __future__ import annotations

import dataclasses
from typing import Iterable


from ...planner import graph
from ...planner import precedence as ranking
from ...model.diagnostics import Diagnostic, shape_mismatches
from ...model.kinds import Kind
from ...model.plans import Seam
from ...model.shapes import Shape
from .claims import BindingClaim, CapabilityContractClaim, NodeClaim, ProviderClaim, ShapeExpectationClaim
from .plan import PlannedNode, TargetPlan


def _parse_ref(ref: str, default_scope: str) -> tuple[str, str]:
    if "." in ref:
        scope, name = ref.split(".", 1)
        return scope, name
    return default_scope, ref


def _union_shape(a: Shape, b: Shape) -> Shape:
    return Shape(members=a.members | b.members, protocols=a.protocols | b.protocols)


def _group_by(claims, key_fn):
    groups: dict = {}
    for c in claims:
        groups.setdefault(key_fn(c), []).append(c)
    return groups


def _dedupe_conflicts(groups: dict, code: str, subject_fn):
    diags = []
    resolved = {}
    for key in sorted(groups, key=repr):
        group = groups[key]
        if len(group) == 1:
            resolved[key] = group[0]
            continue
        contents = {ranking.content_key(c) for c in group}
        winner = sorted(group, key=ranking.sort_key)[0]
        resolved[key] = winner
        if len(contents) > 1:
            diags.append(Diagnostic(code, subject_fn(key), 1))
    return resolved, diags


def resolve_contract_to_node(
    kind: Kind,
    claims: Iterable,
    *,
    precedence: tuple[str, ...] = (),
) -> tuple[TargetPlan | None, tuple[Diagnostic, ...]]:
    """Gate 1's engine. Parameterised by `kind`; contains no branch on a kind's name."""

    # Gate 1 turns "what the target file asks for" and "what packs offer" into one TargetPlan: a node per name, each
    # bound to exactly one provider. It is a pure function of its claims (no I/O, no imports of providers), so
    # the same inputs always give the same plan and a bad target file is diagnosed without touching hardware.
    diags: list[Diagnostic] = []

    contract_claims = [c for c in claims if isinstance(c, CapabilityContractClaim)]
    provider_claims = [c for c in claims if isinstance(c, ProviderClaim)]
    node_claims = [c for c in claims if isinstance(c, NodeClaim)]
    binding_claims = [c for c in claims if isinstance(c, BindingClaim)]
    shape_expectation_claims = [c for c in claims if isinstance(c, ShapeExpectationClaim)]

    def effective_scope(scope: str) -> str:
        return scope if kind.scoped else ""

    # ---- 1.1 index ----
    # Two claims for the same contract (or provider) name collapse when identical and are a conflict when they
    # differ: the vocabulary must be unambiguous before anything is chosen from it.
    contracts_by_token, contract_diags = _dedupe_conflicts(
        _group_by(contract_claims, lambda c: c.token), "CONTRACT_CONFLICT", lambda k: f"contract:{k}"
    )
    providers_by_name, provider_diags = _dedupe_conflicts(
        _group_by(provider_claims, lambda c: c.name), "PROVIDER_CONFLICT", lambda k: f"provider:{k}"
    )
    if contract_diags or provider_diags:
        return None, tuple(sorted(contract_diags + provider_diags, key=lambda d: (d.gate, d.code, d.subject)))

    # Additive, like GoalClaim/RelationClaim in Gate 2: every expectation for the same
    # contract unions into one shape, regardless of which contributor or consumer declared it.
    shape_expectations_by_contract: dict[str, Shape] = {}
    for c in shape_expectation_claims:
        shape_expectations_by_contract[c.contract] = _union_shape(
            shape_expectations_by_contract.get(c.contract, Shape()), c.shape
        )

    # P(contract) = the providers implementing it, sorted: the candidates when a node names no provider.
    providers_by_contract: dict[str, list[str]] = {}
    for name, p in providers_by_name.items():
        providers_by_contract.setdefault(p.implements, []).append(name)
    for lst in providers_by_contract.values():
        lst.sort()

    # ---- 1.2 identity, override, alias ----
    # Several contributors may claim the same node name: the highest-ranked origin wins (precedence is the
    # target file's own origin, then packs). An unresolvable tie is NAME_COLLISION, never an arbitrary pick, because
    # silently choosing a provider is how two setups end up running different code from one target file.
    node_groups = _group_by(node_claims, lambda c: (effective_scope(c.scope), c.name))
    node_winners: dict[str, NodeClaim] = {}
    for key in sorted(node_groups, key=repr):
        group = node_groups[key]
        winner, conflict = ranking.resolve_group(group, precedence)
        ref = f"{key[0]}.{key[1]}"
        node_winners[ref] = winner
        if conflict:
            diags.append(Diagnostic("NAME_COLLISION", ref, 1))

    binding_by_key = _group_by(binding_claims, lambda c: f"{effective_scope(c.scope)}.{c.name}")
    rebound_slots: dict[str, set[str]] = {}
    for key in sorted(binding_by_key):
        group = binding_by_key[key]
        if key not in node_winners or node_winners[key].alias is not None:
            diags.append(Diagnostic("REBIND_ORPHAN", key, 1))
            continue
        per_slot: dict[str, list[tuple[str, str]]] = {}
        for bc in group:
            for slot, ref in bc.bind:
                per_slot.setdefault(slot, []).append((bc.origin, ref))
        winner_claim = node_winners[key]
        bind_dict = dict(winner_claim.bind)
        for slot in sorted(per_slot):
            entries = per_slot[slot]
            if len(entries) == 1:
                bind_dict[slot] = entries[0][1]
            else:
                best_rank = max(ranking.rank(o, precedence) for o, _ in entries)
                top = [e for e in entries if ranking.rank(e[0], precedence) == best_rank]
                values = {v for _, v in top}
                bind_dict[slot] = sorted(top, key=lambda e: e[1])[0][1]
                if len(values) > 1:
                    diags.append(Diagnostic("NAME_COLLISION", f"{key}#{slot}", 1))
            rebound_slots.setdefault(key, set()).add(slot)
        node_winners[key] = dataclasses.replace(winner_claim, bind=tuple(sorted(bind_dict.items())))

    # Aliases form a graph a -> b ("a is another name for b"). A cycle has no real node at its end, so its
    # members are reported and dropped; every other alias is followed to the real node at the end of its chain.
    alias_claims = {k: c for k, c in node_winners.items() if c.alias is not None}
    alias_target: dict[str, str] = {}
    for key, claim in alias_claims.items():
        scope, name = _parse_ref(claim.alias, claim.scope)
        alias_target[key] = f"{effective_scope(scope)}.{name}"

    alias_keys = set(alias_target)
    cycle_edges = frozenset((a, b) for a, b in alias_target.items() if b in alias_keys)
    cycle = graph.find_cycle(alias_keys, cycle_edges)
    if cycle:
        for key in cycle:
            diags.append(Diagnostic("ALIAS_CYCLE", key, 1))
            alias_target.pop(key, None)

    def resolve_alias_chain(key: str, seen: frozenset[str] = frozenset()) -> str | None:
        if key in seen:
            return None
        if key not in alias_target:
            return key if key in node_winners and key not in alias_claims else None
        target = alias_target[key]
        if target not in node_winners:
            return None
        return resolve_alias_chain(target, seen | {key})

    resolved_alias: dict[str, str] = {}
    for key in alias_claims:
        if key not in alias_target:
            continue
        real = resolve_alias_chain(key)
        if real is None:
            diags.append(Diagnostic("ALIAS_UNRESOLVED", key, 1))
        else:
            resolved_alias[key] = real

    # visible[scope][name] = the real node a name in that scope stands for (its own nodes and its aliases).
    visible: dict[str, dict[str, str]] = {}
    for key, claim in node_winners.items():
        if claim.alias is None:
            visible.setdefault(effective_scope(claim.scope), {})[claim.name] = key
    for akey, real in resolved_alias.items():
        aclaim = node_winners[akey]
        visible.setdefault(effective_scope(aclaim.scope), {})[aclaim.name] = real

    real_node_keys: set[str] = {k for k, c in node_winners.items() if c.alias is None}

    def declared_contract(claim: NodeClaim) -> str | None:
        if claim.contract is not None:
            return claim.contract
        if claim.using is not None:
            prov = providers_by_name.get(claim.using)
            return prov.implements if prov else None
        return None

    # I(scope, contract): the nodes a slot of that contract could bind to in that scope. A slot binds without
    # being told exactly when |I| = 1; the index is built once, so binding all slots is linear in their number.
    scope_contract_index: dict[tuple[str, str], set[str]] = {}
    for scope, names in visible.items():
        for name, key in names.items():
            c = declared_contract(node_winners[key])
            if c is not None:
                scope_contract_index.setdefault((scope, c), set()).add(key)

    # ---- 1.3 provider selection (memoised; order-independent) ----
    # provider(node) = the provider it names (which must implement its contract), else the only element of
    # P(contract), else NO_PROVIDER (|P| = 0) or PROVIDER_AMBIGUOUS (|P| > 1). Memoised, so a node is decided
    # once however many slots ask about it, and each diagnostic is emitted once.
    provider_cache: dict[str, tuple[ProviderClaim | None, str | None]] = {}
    provider_diag_emitted: set[str] = set()

    def get_provider(ref: str) -> tuple[ProviderClaim | None, str | None]:
        if ref in provider_cache:
            return provider_cache[ref]
        claim = node_winners[ref]
        if claim.using is not None:
            prov = providers_by_name.get(claim.using)
            if prov is None:
                if ref not in provider_diag_emitted:
                    diags.append(Diagnostic("PROVIDER_UNKNOWN", ref, 1, (("provider", claim.using),)))
                    provider_diag_emitted.add(ref)
                result = (None, None)
            elif claim.contract is not None and prov.implements != claim.contract:
                if ref not in provider_diag_emitted:
                    diags.append(Diagnostic("PROVIDER_CONTRACT_MISMATCH", ref, 1))
                    provider_diag_emitted.add(ref)
                result = (None, None)
            else:
                result = (prov, "explicit-using")
        else:
            contract = claim.contract
            candidates = providers_by_contract.get(contract, []) if contract is not None else []
            if len(candidates) == 0:
                if ref not in provider_diag_emitted:
                    diags.append(Diagnostic("NO_PROVIDER", ref, 1))
                    provider_diag_emitted.add(ref)
                result = (None, None)
            elif len(candidates) > 1:
                if ref not in provider_diag_emitted:
                    diags.append(
                        Diagnostic(
                            "PROVIDER_AMBIGUOUS",
                            ref,
                            1,
                            evidence=tuple(("candidate", c) for c in candidates),
                        )
                    )
                    provider_diag_emitted.add(ref)
                result = (None, None)
            else:
                result = (providers_by_name[candidates[0]], "sole-implementation")
        provider_cache[ref] = result
        return result

    def resolved_contract_of(ref: str) -> str | None:
        claim = node_winners[ref]
        if claim.contract is not None:
            return claim.contract
        prov, _ = get_provider(ref)
        return prov.implements if prov else None

    working_bind: dict[str, dict[str, str]] = {}
    why_bindings: dict[str, dict[str, str]] = {}
    seams: list[Seam] = []

    def given_of(ref: str) -> Shape:
        prov, _ = get_provider(ref)
        token = resolved_contract_of(ref)
        contract_claim = contracts_by_token.get(token) if token else None
        return _union_shape(prov.gives, contract_claim.gives) if contract_claim else prov.gives

    # A seam is one binding seen as an interface: consumer.slot -> provider node. The shape check is set
    # inclusion, E ⊆ G, where
    #   E = what the slot expects ∪ what the consumer's contract says that slot needs ∪ every expectation
    #       declared for the slot's contract (expectations add up, they never replace each other), and
    #   G = what the provider gives ∪ what its contract promises.
    # A member in E \ G is a mismatch, reported with the seam; nothing is trusted on the contract name alone.
    def build_seam(consumer_ref: str, slot: str, need, target_ref: str) -> None:
        target_prov, _ = get_provider(target_ref)
        if target_prov is None:
            return
        given = given_of(target_ref)

        consumer_contract_token = resolved_contract_of(consumer_ref)
        consumer_contract_claim = contracts_by_token.get(consumer_contract_token) if consumer_contract_token else None
        expected = need.expected
        if consumer_contract_claim is not None:
            for n2 in consumer_contract_claim.needs:
                if n2.slot == slot:
                    expected = _union_shape(expected, n2.expected)
                    break
        if need.contract in shape_expectations_by_contract:
            expected = _union_shape(expected, shape_expectations_by_contract[need.contract])

        subject = f"{consumer_ref}#{slot}"
        diags.extend(shape_mismatches(subject, given, expected, 1))

        seams.append(
            Seam(
                consumer=consumer_ref,
                slot=slot,
                provider=target_ref,
                expected=tuple(sorted(m.name for m in expected.members)),
                given=tuple(sorted(m.name for m in given.members)),
            )
        )

    # ---- 1.4 slot binding ----
    # For every slot, in this order: the role the claim binds explicitly (it must exist in the scope and declare
    # the slot's contract), else the only candidate in I(scope, contract), else a diagnostic. There is no third
    # rule: OCTO never creates a node to fill a slot.
    for ref in sorted(real_node_keys):
        claim = node_winners[ref]
        scope = effective_scope(claim.scope)
        prov, _why = get_provider(ref)
        if prov is None:
            continue
        node_bind = dict(claim.bind)
        wb = why_bindings.setdefault(ref, {})
        bd = working_bind.setdefault(ref, {})

        for need in sorted(prov.needs, key=lambda n: n.slot):
            slot = need.slot
            if slot in node_bind:
                refstr = node_bind[slot]
                rscope, rname = _parse_ref(refstr, scope)
                rscope = effective_scope(rscope)
                target_real = visible.get(rscope, {}).get(rname)
                if target_real is None:
                    diags.append(Diagnostic("BINDING_UNKNOWN", f"{ref}#{slot}", 1))
                    continue
                rkey = f"{rscope}.{rname}"
                was_alias = rkey in node_winners and node_winners[rkey].alias is not None
                target_declared = declared_contract(node_winners[target_real])
                if target_declared != need.contract:
                    diags.append(Diagnostic("BINDING_CONTRACT_MISMATCH", f"{ref}#{slot}", 1))
                    continue
                reason = "explicit"
                if slot in rebound_slots.get(ref, ()):
                    reason = "rebind"
                elif was_alias:
                    reason = "alias"
                bd[slot] = target_real
                wb[slot] = reason
                build_seam(ref, slot, need, target_real)
                continue

            candidates = scope_contract_index.get((scope, need.contract), set())
            if len(candidates) == 1:
                target_real = next(iter(candidates))
                bd[slot] = target_real
                wb[slot] = "sole-candidate-in-scope"
                build_seam(ref, slot, need, target_real)
                continue
            if len(candidates) > 1:
                diags.append(
                    Diagnostic(
                        "SLOT_AMBIGUOUS",
                        f"{ref}#{slot}",
                        1,
                        evidence=tuple(("candidate", c) for c in sorted(candidates)),
                    )
                )
                continue

            diags.append(Diagnostic("SLOT_UNSATISFIED", f"{ref}#{slot}", 1))

    # rebind on a slot the selected provider does not have
    for ref, slots in rebound_slots.items():
        if ref not in node_winners or node_winners[ref].alias is not None:
            continue
        prov, _ = get_provider(ref)
        if prov is None:
            continue
        provider_slots = {n.slot for n in prov.needs}
        for slot in slots:
            if slot not in provider_slots:
                diags.append(Diagnostic("REBIND_ORPHAN", f"{ref}#{slot}", 1))

    # ---- 1.5b a declared node no slot binds is still held to its contract's expectations ----
    # Without a consumer there is no seam, but E ⊆ G must still hold for the expectations declared on the
    # contract: a test may use the node directly.
    bound = {s.provider for s in seams}
    for ref in sorted(real_node_keys - bound):
        expected = shape_expectations_by_contract.get(resolved_contract_of(ref) or "")
        if expected is not None and get_provider(ref)[0] is not None:
            diags.extend(shape_mismatches(ref, given_of(ref), expected, 1))

    # ---- 1.6 target graph and order ----
    # An edge (dependency, dependent) for every binding: a node is constructed after everything it binds to.
    # A cycle (a needs b needs a) cannot be constructed in any order and is reported with its path; otherwise
    # the construction order is the deterministic topological order of this graph.
    edges = frozenset((target, ref) for ref, binds in working_bind.items() for target in binds.values())
    cyc = graph.find_cycle(real_node_keys, edges)
    if cyc:
        diags.append(Diagnostic("CYCLE", cyc[0], 1, evidence=(("path", ",".join(cyc)),)))

    if diags:
        return None, tuple(sorted(diags, key=lambda d: (d.gate, d.code, d.subject)))

    construction_order = graph.toposort_kahn(real_node_keys, edges)

    nodes: list[PlannedNode] = []
    for ref in sorted(real_node_keys):
        claim = node_winners[ref]
        prov, why_provider = get_provider(ref)
        contract = claim.contract if claim.contract is not None else prov.implements
        nodes.append(
            PlannedNode(
                scope=effective_scope(claim.scope),
                name=claim.name,
                contract=contract,
                provider=prov.name,
                impl=prov.impl,
                config=tuple(sorted(claim.config)),
                bindings=tuple(sorted(working_bind.get(ref, {}).items())),
                why_provider=why_provider,
                why_bindings=tuple(sorted(why_bindings.get(ref, {}).items())),
                gives=given_of(ref),
            )
        )

    aliases = tuple(sorted(resolved_alias.items()))
    seams_sorted = tuple(sorted(seams, key=lambda s: (s.consumer, s.slot)))

    plan = TargetPlan(
        nodes=tuple(nodes),
        construction_order=construction_order,
        aliases=aliases,
        seams=seams_sorted,
    )
    return plan, ()
