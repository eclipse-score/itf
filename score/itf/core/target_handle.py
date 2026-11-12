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
"""The target handle: one per session, a thin view over the realization.

`target.<role>` is a role of the root scope, `target.dev1.<role>` a role of scope `dev1`. A device
never falls back to the root: what `dev1` should share, the target file lists under `share:`.
Aliased names share the underlying node rather than creating another instance.
"""

from __future__ import annotations

from .engine.config import redact_target
from .engine.scopes import ROOT, TARGET_MEMBERS, VIEW_MEMBERS, display, display_json
from .engine.labels import label_steps, node_label


# The handle is a view, not a store: attribute access fetches (lazily constructing) the node from the
# realization, so `renew` can swap an object and the next `target.x` simply sees the new one.
class ScopeView:
    def __init__(self, session, scope: str):
        self._scope = scope
        self._session = session

    @property
    def scope(self) -> str | None:
        """The device scope's name; `None` for the target's root."""
        return None if self._scope == ROOT else self._scope

    @property
    def _label(self) -> str:
        return "target" if self._scope == ROOT else f"target.{self._scope}"

    def tokens(self) -> tuple[str, ...]:
        return self._session.target_plan.tokens(self._scope)

    def has(self, role: str) -> bool:
        """Whether this scope has the role `role`."""
        return role in self.names()

    def names(self) -> tuple[str, ...]:
        return self._session.target_plan.names(self._scope)

    def get(self, name: str):
        if name not in self.names():
            raise KeyError(f"{self._label} has no {name!r}; known: {', '.join(self.names()) or '(nothing)'}")
        return self._session._realization.get(f"{self._scope}.{name}")

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self.get(name)
        except KeyError as exc:
            raise AttributeError(str(exc)) from exc

    def __repr__(self) -> str:
        return f"<{self._label}: {', '.join(self.names()) or '(no roles)'}>"

    def states(self) -> frozenset[str]:
        """States held at the last probe, restricted to this scope, unqualified."""
        prefix = f"{self._scope}:"
        return frozenset(s[len(prefix) :] for s in self._session.observed if s.startswith(prefix))

    def probe(self, *states: str) -> frozenset[str]:
        """Run the probes (of `states`, or of every state) and return what holds in this scope, unqualified."""
        prefix = f"{self._scope}:"
        wanted = frozenset(f"{prefix}{s}" for s in states) if states else None
        holds = self._session.probe(wanted)
        return frozenset(s[len(prefix) :] for s in holds if s.startswith(prefix))

    def reach(self, *states: str, assume: tuple[str, ...] = (), reason: str = "", owner: str = ""):
        """`session.reach` with unqualified states and assumptions taken to mean this scope."""
        q = lambda s: s if ":" in s else f"{self._scope}:{s}"
        return self._session.reach(*map(q, states), assume=tuple(map(q, assume)), reason=reason, owner=owner)

    def renew(self, *names: str):
        """`session.renew` with bare role names taken to mean this scope (`.name` is the root)."""
        q = lambda n: n if n.startswith(".") or "." in n else f"{self._scope}.{n}"
        return self._session.renew(*map(q, names))

    def discard(self, *names: str) -> None:
        """`session.discard` with bare role names taken to mean this scope (`.name` is the root)."""
        q = lambda n: n if n.startswith(".") or "." in n else f"{self._scope}.{n}"
        self._session.discard(*map(q, names))

    def plan(self) -> dict:
        tp = _redacted(self._session)
        ap = self._session.action_plan
        return display_json(
            {
                "target": {k: v for k, v in tp.to_json().items() if k != "nodes"}
                | {"nodes": [n for n in _labelled(tp.to_json()["nodes"]) if n["scope"] == self._scope]},
                "action": {k: v for k, v in ap.to_json().items() if k != "steps"}
                | {
                    "steps": [
                        s
                        for s in label_steps(ap.to_json(), self._session.catalog)["steps"]
                        if any(d.startswith(f"{self._scope}:") for d in s["delivers"])
                    ]
                },
            }
        )


class Target(ScopeView):
    """The whole target: the root scope's roles as attributes, each device scope as `target.<name>`."""

    def __init__(self, session, scopes):
        super().__init__(session, ROOT)
        self._scopes = {name: ScopeView(session, name) for name in sorted(scopes)}

    def scopes(self) -> tuple[str, ...]:
        return tuple(self._scopes)

    def get(self, name: str):
        if name in self._scopes and name not in self.names():
            raise KeyError(f"{name!r} is a device scope, not a role: use target.{name}")
        return super().get(name)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._scopes:
            return self._scopes[name]
        if name in self.names():
            return self.get(name)
        raise AttributeError(
            f"target has no role or scope {name!r}; roles: {', '.join(self.names()) or '(none)'}; "
            f"scopes: {', '.join(self._scopes) or '(none)'}"
        )

    def __repr__(self) -> str:
        return (
            f"<target: {', '.join(self.names()) or '(no roles)'}"
            f"{'; scopes: ' + ', '.join(self._scopes) if self._scopes else ''}>"
        )

    def plan(self) -> dict:
        return {
            "target": target_view(_redacted(self._session), self._scopes),
            "action": display_json(label_steps(self._session.action_plan.to_json(), self._session.catalog)),
        }


def _redacted(session):
    return redact_target(session.target_plan, getattr(session.catalog, "config_schemas", {}))


def _labelled(nodes: list) -> list:
    """Each role of a plan with its `label` (`command (store)`, `gw.command (store:sim)`): how a person reads it."""
    return [{**n, "label": node_label(display(f"{n['scope']}.{n['name']}"), n["provider"])} for n in nodes]


def target_view(target_plan, scopes=()) -> dict:
    """The target plan shaped like the handle: root roles, then one entry per device scope."""
    data = target_plan.to_json()
    nodes = _labelled(data.pop("nodes"))
    root = [n for n in nodes if n["scope"] == ROOT]
    by_scope: dict = {name: {"nodes": []} for name in scopes}
    for n in nodes:
        if n["scope"] != ROOT:
            by_scope.setdefault(n["scope"], {"nodes": []})["nodes"].append(n)
    return display_json({"nodes": root, "scopes": dict(sorted(by_scope.items())), **data})


def name_clashes(target_plan, scopes) -> tuple[str, ...]:
    """Names `target.<x>` / `target.<scope>.<x>` could not resolve unambiguously."""
    clashes = []
    root_names = set(target_plan.names(ROOT))
    for name in sorted(root_names & set(scopes)):
        clashes.append(f"target.{name} is both a root role and a device scope")
    for name in sorted(root_names & TARGET_MEMBERS):
        clashes.append(f"target.{name} shadows the handle's own member {name!r}")
    for scope in sorted(scopes):
        for name in sorted(set(target_plan.names(scope)) & VIEW_MEMBERS):
            clashes.append(f"target.{scope}.{name} shadows the handle's own member {name!r}")
    return tuple(clashes)
