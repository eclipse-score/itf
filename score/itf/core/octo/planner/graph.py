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

from graphlib import CycleError, TopologicalSorter
from heapq import heapify, heappop, heappush
from typing import Iterable


def toposort_kahn(vertices: Iterable[str], edges: frozenset[tuple[str, str]]) -> tuple[str, ...]:
    """Return a deterministic topological order, omitting vertices blocked by cycles."""
    verts = sorted(set(vertices))
    known = set(verts)
    sorter = TopologicalSorter()
    for vertex in verts:
        sorter.add(vertex)
    for before, after in sorted(edges):
        if before not in known:
            raise KeyError(before)
        if after not in known:
            raise KeyError(after)
        sorter.add(after, before)
    try:
        sorter.prepare()
    except CycleError:
        pass
    ready = list(sorter.get_ready())
    heapify(ready)
    order = []
    while ready:
        vertex = heappop(ready)
        order.append(vertex)
        sorter.done(vertex)
        for successor in sorter.get_ready():
            heappush(ready, successor)
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
