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
"""Generic graph algorithms shared by both gates: toposort, cycle detection and reachability.
None of this names a kind."""

from __future__ import annotations

from typing import Iterable


def toposort_kahn(vertices: Iterable[str], edges: frozenset[tuple[str, str]]) -> tuple[str, ...]:
    """Kahn's algorithm; the ready set is popped lexicographically smallest first, always.

    A topological order of a directed graph G = (V, E) is a sequence of V in which, for every edge (a, b),
    a comes before b. Kahn's algorithm builds it greedily: a vertex with no remaining incoming edge
    (in-degree 0) has nothing left that must precede it, so it can be emitted; emitting it removes its
    outgoing edges, which may bring successors to in-degree 0. Every vertex is emitted exactly when its
    last predecessor has been, so the order respects every edge.

    If G has a cycle, the vertices on it never reach in-degree 0 and are missing from the result; callers
    run `find_cycle` first and report the cycle instead.

    Determinism is the point: equal inputs give the same order on every machine and run, so plans
    can be compared, cached and reviewed. Do not replace with an unordered set walk. The sorted ready
    list costs O(V log V) per pop, O(V^2 log V) in all; plans have tens to hundreds of vertices.
    """
    verts = sorted(set(vertices))
    incoming: dict[str, set[str]] = {v: set() for v in verts}
    outgoing: dict[str, set[str]] = {v: set() for v in verts}
    for a, b in edges:
        outgoing[a].add(b)
        incoming[b].add(a)

    # in-degree 0 at the start: the sources of the graph
    ready = sorted(v for v in verts if not incoming[v])
    order: list[str] = []
    remaining_incoming = {v: set(s) for v, s in incoming.items()}
    while ready:
        ready.sort()
        v = ready.pop(0)
        order.append(v)
        for nxt in sorted(outgoing[v]):
            # "remove" the edge v -> nxt; nxt is ready once its last predecessor is emitted
            remaining_incoming[nxt].discard(v)
            if not remaining_incoming[nxt]:
                ready.append(nxt)
    return tuple(order)


def find_cycle(vertices: Iterable[str], edges: frozenset[tuple[str, str]]) -> tuple[str, ...] | None:
    """Returns one cycle's path, rotated to start at its lowest-sorted vertex, or None.

    Depth-first search with three colours: WHITE (not visited yet), GRAY (on the current search path),
    BLACK (finished: every vertex reachable from it has been explored). An edge into a GRAY vertex is a
    back edge, and a directed graph has a cycle exactly when a depth-first search finds a back edge: the
    cycle is the part of the current path from that GRAY vertex to here. An edge into a BLACK vertex
    cannot close a cycle, since that vertex's whole reach was already explored. O(V + E).

    Rotating the cycle to its smallest vertex makes the report independent of where the search started.
    """
    verts = sorted(set(vertices))
    outgoing: dict[str, list[str]] = {v: [] for v in verts}
    for a, b in edges:
        outgoing[a].append(b)
    for v in outgoing:
        outgoing[v].sort()

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {v: WHITE for v in verts}
    stack_path: list[str] = []

    def visit(v: str) -> tuple[str, ...] | None:
        color[v] = GRAY
        stack_path.append(v)
        for nxt in outgoing[v]:
            if color[nxt] == GRAY:  # a back edge: nxt is on the current path, so the path closes a cycle
                idx = stack_path.index(nxt)
                cycle = stack_path[idx:]
                return _rotate_to_min(cycle)
            if color[nxt] == WHITE:
                found = visit(nxt)
                if found is not None:
                    return found
        stack_path.pop()
        color[v] = BLACK
        return None

    for v in verts:
        if color[v] == WHITE:
            found = visit(v)
            if found is not None:
                return found
    return None


def _rotate_to_min(path: list[str]) -> tuple[str, ...]:
    lo = min(range(len(path)), key=lambda i: path[i])
    return tuple(path[lo:] + path[:lo])


def reachable_pairs(vertices: Iterable[str], edges: frozenset[tuple[str, str]]) -> frozenset[tuple[str, str]]:
    """All (a, b) such that a directed path a -> ... -> b exists: the transitive closure of the edges.

    One depth-first walk from every vertex, so O(V * (V + E)); exact and simple at plan sizes. Gate 2 uses
    it as the starting point of the "already ordered before" relation it then keeps up to date itself.
    """
    verts = sorted(set(vertices))
    outgoing: dict[str, set[str]] = {v: set() for v in verts}
    for a, b in edges:
        outgoing[a].add(b)

    pairs: set[tuple[str, str]] = set()
    for start in verts:
        seen: set[str] = set()
        stack = list(outgoing[start])
        while stack:
            nxt = stack.pop()
            if nxt in seen:
                continue
            seen.add(nxt)
            pairs.add((start, nxt))
            stack.extend(outgoing[nxt] - seen)
    return frozenset(pairs)
