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
"""The target file format: one YAML document says what a target is made of.

    include:                        # merged first, in order; this file wins
      - base.itf.yaml
        policies:                       # explicit files, relative to invocation cwd or absolute
            - policies/common.py
    capabilities:                   # keyed by role: the name tests use (`target.command`)
      platform:
        factory: acme.platform    # <pack>.<capability factory>
        with:                       # the factory's settings, checked against its config dataclass
          image: my-image:latest
      command: acme.exec            # short form: just the factory
      shell:
        factory: acme.shell
        bind:                       # only when a slot has more than one candidate: slot -> role
          endpoint: lab_endpoint
    actions:                        # how an action's slots are filled, when a slot has more than one candidate
      acme.open:                    # an action label
        bind:
          endpoint: lab_endpoint    # slot -> role of this scope
    goals:                          # state contracts to reach; nothing is inferred
      - platform.up
      - state: console.open
        by: acme.open               # only when two listed packs have an action making it true
    relations:                      # a third party's temporal relations between states, added to the actions' own
      - state: platform.up          # an action of a listed pack makes this true
        after:                      # ... only once these hold
          - console.open
        breaks:                     # ... and it destroys these
          - network.reachable
    assume:
      - state: rack.ready
        owner: lab
        reason: the rack keeps it on
    scopes:                         # one more device of a multi-device target
      gw:
        capabilities:
          command: acme.exec
        goals:
          - shell.open
        actions:                    # same entries; the roles are this scope's
          acme.open:
            bind:
              endpoint: command
        relations:                  # same entries; `state` and its `after`/`breaks` are in this scope
          - state: shell.open
            after:
              - platform.up
        share:
          - platform                # gw uses the root's platform role

An override file is a target file holding only what changes; it is merged by role like an include, after
the target. `${NAME}` / `${NAME:-default}` in a `with:` value reads the environment (`$${` is a literal
`${`); a value that is exactly one reference is read as a YAML scalar, so `port: ${SSH_PORT:-22}` is an int.

Translation to the planner is direct: a role becomes a role of the scope, its factory the part that builds it,
`with` its settings, `bind` its slot-to-role choices, `share` an alias to the root role, goals goal claims, `by` the
chosen action, `actions:` the slot-to-role choices of an action in that scope, `relations` the listed state's
`after` and `breaks` added to the claim of the action that makes it true (a state no listed action makes or
assumes is a compile error).

The actions considered are those of the packs of the listed factories plus the project's own. An action fills
each of its slots with the role `actions:` names, else the one role of the slot's contract in the scope, else it
cannot run there. An action is a candidate for a state in a scope only when all its slots can be filled that way;
a state two candidates could make true, with no `by`, is a compile error naming both. No capability enters a
target unless the target file lists it.
"""

from __future__ import annotations

import copy
import dataclasses
import os
import re
from pathlib import Path
from typing import Any, Mapping

import yaml

from ..engine.config import Unset
from ..engine.yaml_text import safe_load as yaml_safe_load

from ..engine.packs import pack_of
from ..engine.publish import Catalog
from ..engine.scopes import ROOT, check_scope_name, node_ref, state_ref
from ..octo import AssumeClaim, GoalClaim, NodeClaim, StateContractClaim
from .target_source import read_document

TARGET_FILE_ORIGIN = "target file"
KEYS = ("include", "policies", "packs", "capabilities", "actions", "goals", "relations", "assume", "scopes")
SCOPE_KEYS = ("capabilities", "actions", "goals", "relations", "share")
ACTION_KEYS = ("bind",)
RELATION_KEYS = ("state", "after", "breaks")
ENTRY_KEYS = ("factory", "with", "bind", "remove")


class TargetFileError(ValueError):
    """The target file cannot be compiled; the message names what is wrong and what to write instead."""


# ---- reading and merging ------------------------------------------------------------------------------------


def read(source: Any) -> tuple[Mapping[str, Any], Path | None]:
    """`source` as (document, path-or-None): a parsed mapping, a path, or inline YAML/JSON text."""
    if isinstance(source, Mapping):
        return source, None
    text, path = read_document(getattr(source, "value", source))
    where = path or "target file"
    try:
        doc = yaml_safe_load(text)
    except yaml.YAMLError as exc:
        raise TargetFileError(f"{where} is not valid YAML: {exc}") from exc
    doc = doc or {}
    if not isinstance(doc, Mapping):
        raise TargetFileError(f"{where}: a target file is a mapping, not {type(doc).__name__}")
    return doc, path


def _entry(role: str, entry: Any, where: str) -> dict:
    if entry is None:
        return {}
    if isinstance(entry, str):
        return {"factory": entry}
    if isinstance(entry, Mapping):
        unknown = sorted(set(entry) - set(ENTRY_KEYS))
        if unknown:
            raise TargetFileError(
                f"{where}: role {role!r} has unknown key(s) {', '.join(unknown)}; a role has {', '.join(ENTRY_KEYS)}"
            )
        for key in ("with", "bind"):
            if entry.get(key) is not None and not isinstance(entry[key], Mapping):
                raise TargetFileError(f"{where}: role {role!r}: {key} is a mapping")
        if "remove" in entry and (entry["remove"] is not True or len(entry) > 1):
            raise TargetFileError(f"{where}: role {role!r}: `remove: true` stands alone; it takes the role out")
        return {k: copy.deepcopy(v) for k, v in entry.items() if v is not None}
    raise TargetFileError(f"{where}: role {role!r} is `<pack>.<factory>` or a mapping, not {entry!r}")


def _capabilities(value: Any, where: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TargetFileError(f"{where}: capabilities is a mapping of role to factory")
    return {str(role): _entry(str(role), entry, where) for role, entry in value.items()}


def _action_entry(label: Any, entry: Any, where: str) -> dict:
    entry = {} if entry is None else entry
    if not isinstance(entry, Mapping):
        raise TargetFileError(f"{where}: action {label!r} is a mapping with `bind:`, not {entry!r}")
    unknown = sorted(set(entry) - set(ACTION_KEYS))
    if unknown:
        raise TargetFileError(
            f"{where}: action {label!r} has unknown key(s) {', '.join(map(str, unknown))}; an action has "
            f"{', '.join(ACTION_KEYS)}"
        )
    bind = entry.get("bind") or {}
    if not isinstance(bind, Mapping) or not all(isinstance(k, str) and isinstance(v, str) for k, v in bind.items()):
        raise TargetFileError(f"{where}: action {label!r}: bind maps a slot to a role name")
    return {"bind": dict(bind)}


def _actions(value: Any, where: str) -> dict:
    """`actions:` as {action label: {"bind": {slot: role}}}."""
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TargetFileError(f"{where}: actions is a mapping of action label to its entry")
    return {str(label): _action_entry(label, entry, where) for label, entry in value.items()}


def _merge_actions(base: dict, over: dict) -> dict:
    return {
        label: {"bind": {**base.get(label, {}).get("bind", {}), **over.get(label, {}).get("bind", {})}}
        for label in dict.fromkeys([*base, *over])
    }


def _goal(goal: Any, where: str) -> dict:
    if isinstance(goal, str):
        return {"state": goal}
    if isinstance(goal, Mapping) and isinstance(goal.get("state"), str) and set(goal) <= {"state", "by"}:
        return dict(goal)
    raise TargetFileError(f"{where}: a goal is a state name, or `state:` with an optional `by:`; not {goal!r}")


def _names(value: Any, where: str, key: str, state: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise TargetFileError(f"{where}: relation of {state!r}: {key} is a list of state names")
    return list(value)


def _relation(item: Any, where: str) -> dict:
    if not (isinstance(item, Mapping) and isinstance(item.get("state"), str) and set(item) <= set(RELATION_KEYS)):
        raise TargetFileError(
            f"{where}: a relation is `state:` with `after:` and/or `breaks:` (lists of states); not {item!r}"
        )
    state = item["state"]
    after, breaks = (_names(item.get(key), where, key, state) for key in ("after", "breaks"))
    if not after and not breaks:
        raise TargetFileError(f"{where}: relation of {state!r} has neither `after` nor `breaks`")
    return {"state": state, "after": after, "breaks": breaks}


def _merge_relations(base: list, extra: list) -> list:
    """By state; the lists of one state are joined, so an include and its includer both add."""
    merged = {
        item["state"]: {"state": item["state"], "after": list(item["after"]), "breaks": list(item["breaks"])}
        for item in base
    }
    for item in extra:
        mine = merged.setdefault(item["state"], {"state": item["state"], "after": [], "breaks": []})
        for key in ("after", "breaks"):
            mine[key] = list(dict.fromkeys([*mine[key], *item[key]]))
    return list(merged.values())


def _assume(item: Any, where: str) -> dict:
    entry = {"state": item} if isinstance(item, str) else item
    if not (
        isinstance(entry, Mapping)
        and isinstance(entry.get("state"), str)
        and set(entry) <= {"state", "owner", "reason"}
    ):
        raise TargetFileError(f"{where}: an assumption is `state:` with optional `owner:` and `reason:`; not {item!r}")
    return dict(entry)


def _by_state(base: list, extra: list) -> list:
    merged = {item["state"]: item for item in base}
    for item in extra:
        merged[item["state"]] = {**merged.get(item["state"], {}), **item}
    return list(merged.values())


def _merge_caps(base: dict, over: dict) -> dict:
    out = {role: dict(entry) for role, entry in base.items()}
    for role, entry in over.items():
        if entry.get("remove"):
            # An override or includer takes the role out; the marker travels on until the final merge, since a
            # file is first merged over an empty base where there is nothing to remove yet.
            if role in out and not out[role].get("remove"):
                out.pop(role)
            else:
                out[role] = {"remove": True}
            continue
        mine = out.setdefault(role, {})
        if "factory" in entry and entry["factory"] != mine.get("factory"):
            mine.clear()  # another factory: the old one's settings and bindings do not carry over
        for key, value in entry.items():
            mine[key] = {**mine.get(key, {}), **value} if key in ("with", "bind") else value
    return out


def _share(value: Any, name: str, where: str) -> list:
    share = value or []
    if not isinstance(share, list) or not all(isinstance(s, str) for s in share):
        raise TargetFileError(f"{where}: scope {name!r}: share is a list of root role names")
    return list(share)


def _scope(scope: Any, name: str, where: str) -> dict:
    if scope is None:
        scope = {}
    if not isinstance(scope, Mapping):
        raise TargetFileError(f"{where}: scope {name!r} is a mapping")
    unknown = sorted(set(scope) - set(SCOPE_KEYS))
    if unknown:
        raise TargetFileError(
            f"{where}: scope {name!r} has unknown key(s) {', '.join(unknown)}; it has {', '.join(SCOPE_KEYS)}"
        )
    share = _share(scope.get("share"), name, where)
    return {
        "capabilities": _capabilities(scope.get("capabilities"), where),
        "actions": _actions(scope.get("actions"), where),
        "goals": [_goal(g, where) for g in scope.get("goals") or ()],
        "relations": [_relation(r, where) for r in scope.get("relations") or ()],
        "share": share,
    }


def _packs(value: Any, where: str) -> dict:
    """`packs:` names where a pack that is not installed lives: pack name -> module of its entrypoint."""
    if value is None:
        return {}
    if not isinstance(value, Mapping) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise TargetFileError(f"{where}: packs maps a pack name to the module of its entrypoint (acme: acme.plugin)")
    return dict(value)


def _normalise(doc: Mapping, where: str) -> dict:
    unknown = sorted(set(doc) - set(KEYS))
    if unknown:
        raise TargetFileError(f"{where}: unknown key(s) {', '.join(unknown)}; a target file has {', '.join(KEYS)}")
    return {
        **({"policies": _policies(doc["policies"], where)} if "policies" in doc else {}),
        "_clear_policies": doc.get("policies") == [],
        "packs": _packs(doc.get("packs"), where),
        "capabilities": _capabilities(doc.get("capabilities"), where),
        "actions": _actions(doc.get("actions"), where),
        "goals": [_goal(g, where) for g in doc.get("goals") or ()],
        "relations": [_relation(r, where) for r in doc.get("relations") or ()],
        "assume": [_assume(a, where) for a in doc.get("assume") or ()],
        "scopes": {str(n): _scope(s, str(n), where) for n, s in _scopes(doc.get("scopes"), where).items()},
    }


def _policies(value: Any, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(path, str) and path.strip() for path in value):
        raise TargetFileError(f"{where}: policies is a list of non-empty file paths")
    return list(dict.fromkeys(value))


def _scopes(value: Any, where: str) -> Mapping:
    scopes = value or {}
    if not isinstance(scopes, Mapping):
        raise TargetFileError(f"{where}: scopes is a mapping of name to scope")
    return scopes


def _merge(base: dict, over: dict) -> dict:
    scopes = {n: dict(s) for n, s in base["scopes"].items()}
    for name, scope in over["scopes"].items():
        mine = scopes.setdefault(name, {"capabilities": {}, "actions": {}, "goals": [], "relations": [], "share": []})
        scopes[name] = {
            "capabilities": _merge_caps(mine["capabilities"], scope["capabilities"]),
            "actions": _merge_actions(mine["actions"], scope["actions"]),
            "goals": _by_state(mine["goals"], scope["goals"]),
            "relations": _merge_relations(mine["relations"], scope["relations"]),
            "share": list(dict.fromkeys([*mine["share"], *scope["share"]])),
        }
    return {
        "policies": list(
            dict.fromkeys([*([] if over.get("_clear_policies") else base["policies"]), *over.get("policies", [])])
        ),
        "_clear_policies": base.get("_clear_policies", False) or over.get("_clear_policies", False),
        "packs": {**base["packs"], **over["packs"]},
        "capabilities": _merge_caps(base["capabilities"], over["capabilities"]),
        "actions": _merge_actions(base["actions"], over["actions"]),
        "goals": _by_state(base["goals"], over["goals"]),
        "relations": _merge_relations(base["relations"], over["relations"]),
        "assume": _by_state(base["assume"], over["assume"]),
        "scopes": scopes,
    }


EMPTY = {
    "policies": [],
    "packs": {},
    "capabilities": {},
    "actions": {},
    "goals": [],
    "relations": [],
    "assume": [],
    "scopes": {},
}


def load(source: Any, *, _seen: frozenset = frozenset()) -> dict:
    """One effective document: `include`s merged first (in order), then the file itself, which wins."""
    doc, path = read(source)
    where = str(path) if path is not None else "target file"
    if path is not None:
        if path in _seen:
            raise TargetFileError(f"include cycle at {path}")
        _seen = _seen | {path}
    includes = doc.get("include") or []
    if isinstance(includes, str):
        includes = [includes]
    effective = copy.deepcopy(EMPTY)
    for name in includes:
        target = (path.parent / name) if path is not None else Path(name)
        if path is not None and not target.exists() and Path(name).is_file():
            target = Path(name)  # a generated parent, named by its path from the working directory
        if not target.is_file():
            raise TargetFileError(f"{where}: include {name!r} is not a file (looked for {target})")
        effective = _merge(effective, load(target, _seen=_seen))
    return _merge(effective, _normalise(doc, where))


DOTENV = ".env"


def load_all(target: Any, overrides=()) -> dict:
    """The target with every override file merged over it by role, in order; removed roles are gone. The
    `.env` file beside the target file, when there is one, supplies `${NAME}` values the environment does not."""
    doc = load(target)
    for override in overrides:
        doc = _merge(doc, load(override))
    return {**_without_removed(doc), "_dotenv": _dotenv_of(target)}


def _dotenv_of(target: Any) -> dict:
    """{"path": the .env file looked for (None for inline text), "values": NAME -> value}."""
    if isinstance(target, Mapping):
        return {"path": None, "values": {}}
    _, path = read_document(getattr(target, "value", target))
    if path is None:
        return {"path": None, "values": {}}
    dotenv = Path(path).parent / DOTENV
    return {"path": str(dotenv), "values": read_dotenv(dotenv) if dotenv.is_file() else {}}


def read_dotenv(path: Path) -> dict[str, str]:
    """NAME=value lines; blank lines and `#` comments are skipped, `export ` is allowed, one pair of quotes
    around a value is removed. Nothing is expanded."""
    values = {}
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, value = line.removeprefix("export ").partition("=")
        if not sep or not name.strip().isidentifier():
            raise TargetFileError(f"{path}:{number}: write NAME=value")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name.strip()] = value
    return values


def _without_removed(doc: dict) -> dict:
    keep = lambda caps: {r: e for r, e in caps.items() if not e.get("remove")}  # noqa: E731
    return {
        **doc,
        "capabilities": keep(doc["capabilities"]),
        "scopes": {n: {**s, "capabilities": keep(s["capabilities"])} for n, s in doc["scopes"].items()},
    }


# ---- environment values ---------------------------------------------------------------------------------------

_ENV_REF = re.compile(r"\$(\$)?\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _expand(value: Any, where: str, dotenv: Mapping | None = None, placeholders: bool = False) -> Any:
    """`${NAME}` from the environment, else the target file's `.env`, else `${NAME:-default}`; else, with
    `placeholders`, the value is kept as `Unset("${NAME}")` (a plan-only compile), otherwise it is an error."""
    if not isinstance(value, str) or "${" not in value:
        return value
    dotenv = dotenv or {"path": None, "values": {}}

    def substitute(match: re.Match) -> str:
        escaped, name, default = match.groups()
        if escaped:
            return match.group(0)[1:]
        if name in os.environ:
            return os.environ[name]
        if name in dotenv["values"]:
            return dotenv["values"][name]
        if default is not None:
            return default
        if placeholders:
            missing.append(name)
            return match.group(0)
        also = f" or in {dotenv['path']}" if dotenv["path"] else ""
        raise TargetFileError(f"{where} references ${{{name}}}, which is not set in the environment{also}")

    missing: list[str] = []
    whole = _ENV_REF.fullmatch(value)
    expanded = _ENV_REF.sub(substitute, value)
    if missing:
        return Unset(expanded)
    if whole and not whole.group(1):
        return yaml_safe_load(expanded) if expanded else expanded
    return expanded


# ---- compiling ------------------------------------------------------------------------------------------------


def factory_labels(doc: Mapping) -> tuple[str, ...]:
    """Every factory label the target file names, in every scope."""
    caps = [doc["capabilities"], *(s["capabilities"] for s in doc["scopes"].values())]
    labels = tuple(dict.fromkeys(e["factory"] for c in caps for e in c.values() if "factory" in e))
    for label in labels:
        if not isinstance(label, str) or "." not in label.strip("."):
            raise TargetFileError(f"{label!r} is not a capability factory label; write it as <pack>.<name>")
    return labels


def pack_modules(doc: Mapping) -> dict:
    """The target file's `packs:`: where packs that are not installed live."""
    modules = dict(doc.get("packs") or {})
    if "local" in modules:
        raise TargetFileError("packs: the pack name 'local' is reserved for the project's policy (policy.py)")
    return modules


def packs_of(doc: Mapping) -> tuple[str, ...]:
    return tuple(dict.fromkeys(pack_of(label) for label in factory_labels(doc)))


@dataclasses.dataclass(frozen=True)
class Compiled:
    setup: frozenset  # node claims
    init: frozenset  # goal, assumption and chosen-action claims
    roles: dict  # scope -> {role: factory label}
    pins: dict  # (scope, state) -> action label


def _unknown_label(label: str, catalog: Catalog, kind: str, where: str) -> TargetFileError:
    pack = pack_of(label)
    table = catalog.factories if kind == "factory" else catalog.action_descs
    same = sorted(l for l in table if pack_of(l) == pack)
    if same:
        hint = f"pack {pack} has: {', '.join(same)}"
    else:
        hint = f"no loaded pack is named {pack!r}; loaded: {', '.join(catalog.packs()) or '(none)'}"
    what = "capability factory" if kind == "factory" else "action"
    return TargetFileError(f"{where}: {label!r} is not a known {what}; {hint}")


def _scope_name(name: str) -> str:
    return ROOT if name == ROOT else check_scope_name(name)


def compile(doc: Mapping, catalog: Catalog, *, placeholders: bool = False) -> Compiled:
    """Translate an effective document into claims, checking everything the engine cannot say in these terms.
    `placeholders` keeps a `${NAME}` without a value as `Unset` instead of failing (plan-only sessions)."""
    scopes = {
        ROOT: {
            "capabilities": doc["capabilities"],
            "actions": doc["actions"],
            "goals": doc["goals"],
            "relations": doc["relations"],
            "share": [],
        }
    }
    for name, scope in doc["scopes"].items():
        scopes[_scope_name(name)] = scope
    setup: set = set()
    roles: dict[str, dict] = {}
    for scope_name, scope in scopes.items():
        roles[scope_name] = {}
        setup.update(_role_claims(scope_name, scope, catalog, roles[scope_name], doc.get("_dotenv"), placeholders))
        setup.update(_share_claims(scope_name, scope, doc, roles))
    init, pins = _StateCompiler(doc, scopes, roles, catalog).claims()
    return Compiled(frozenset(setup), frozenset(init), roles, pins)


def _shown(scope_name: str) -> str:
    return "" if scope_name == ROOT else f"scope {scope_name}: "


def _role_claims(
    scope_name: str, scope: Mapping, catalog: Catalog, mine: dict, dotenv: Mapping | None = None, placeholders=False
) -> list:
    """The claims of one scope's roles; fills `mine` with role -> factory label."""
    claims = []
    for role, entry in scope["capabilities"].items():
        where = f"{_shown(scope_name)}role {role!r}"
        if not role.isidentifier() or role.startswith("_"):
            raise TargetFileError(f"{where}: a role is a Python identifier (it becomes target.{role})")
        label = entry.get("factory")
        if label is None:
            raise TargetFileError(
                f"{where}: no factory; write `{role}: <pack>.<factory>` or give `factory:` "
                "(an override file may only change a role the target already has)"
            )
        if label not in catalog.factories:
            raise _unknown_label(label, catalog, "factory", where)
        bind = entry.get("bind") or {}
        _check_slots(where, label, {n.slot for n in catalog.factories[label].needs}, bind)
        with_ = {
            k: _expand(v, f"{where} with {k!r}", dotenv, placeholders) for k, v in (entry.get("with") or {}).items()
        }
        mine[role] = label
        claims.append(
            NodeClaim(
                scope=scope_name,
                name=role,
                using=label,
                bind=tuple(sorted(bind.items())),
                config=tuple(sorted(with_.items())),
                origin=TARGET_FILE_ORIGIN,
            )
        )
    return claims


def _check_slots(where: str, label: str, slots: set, bind: Mapping) -> None:
    stray = sorted(set(bind) - slots)
    if stray:
        raise TargetFileError(
            f"{where}: {label} has no slot {', '.join(map(repr, stray))}; its slots are: "
            f"{', '.join(sorted(slots)) or '(none)'}"
        )


def _share_claims(scope_name: str, scope: Mapping, doc: Mapping, roles: dict) -> list:
    claims = []
    for role in scope["share"]:
        if role not in doc["capabilities"]:
            raise TargetFileError(
                f"{_shown(scope_name)}share names {role!r}, which is not a role of the root; roles: "
                f"{', '.join(doc['capabilities']) or '(none)'}"
            )
        roles[scope_name][role] = roles[ROOT].get(role)
        claims.append(NodeClaim(scope=scope_name, name=role, alias=node_ref(f".{role}"), origin=TARGET_FILE_ORIGIN))
    return claims


class _StateCompiler:
    """The action side of a target file: which action makes each state in each scope, with which slot choices.

    An action is a candidate for a state in a scope only when each of its slots can be filled there: by the
    role `actions:` names, else by the one role of the slot's contract. Of several candidates `by:` chooses;
    without it the state is ambiguous, which is an error naming the candidates."""

    def __init__(self, doc, scopes, roles, catalog: Catalog):
        self.doc, self.scopes, self.roles, self.catalog = doc, scopes, roles, catalog
        listed = {pack_of(label) for per_scope in roles.values() for label in per_scope.values() if label} | {"local"}
        self.considered = {l: d for l, d in catalog.action_descs.items() if d.pack in listed}
        self.by_token = self._index_by_state()
        self.multi = {t for t, labels in self.by_token.items() if len(labels) > 1}
        self.assumed = {item["state"] for item in doc["assume"]}
        self.binds = self._binds()
        self.pins: dict[tuple, str] = {}
        self.chosen: dict[tuple, str] = {}  # (scope, state) -> action label, for states that have several actions
        self.overrides: dict[tuple, StateContractClaim] = {}

    # -- inputs ------------------------------------------------------------------------------------------

    def _index_by_state(self) -> dict:
        """state -> labels of the considered actions that make it true."""
        by_token: dict[str, list[str]] = {}
        for label in sorted(self.considered):
            for claim in self.catalog.action_claims[label]:
                for token in (claim.token, *claim.also_delivers):
                    if label not in by_token.setdefault(token, []):
                        by_token[token].append(label)
        return by_token

    def _binds(self) -> dict:
        """(scope, action label) -> {slot: role}, checked against the catalog and the scope's roles."""
        binds = {}
        for scope_name, scope in self.scopes.items():
            for label, entry in scope["actions"].items():
                where = f"{_shown(scope_name)}actions {label!r}"
                self._known_action(label, where)
                slots = {n.slot for n in self.catalog.action_descs[label].uses}
                _check_slots(where, label, slots, entry["bind"])
                for slot, role in entry["bind"].items():
                    if role not in self.roles[scope_name]:
                        raise TargetFileError(
                            f"{where}: slot {slot!r} is bound to role {role!r}, which this scope does not have; "
                            f"roles: {', '.join(sorted(self.roles[scope_name])) or '(none)'}"
                        )
                binds[(scope_name, label)] = dict(entry["bind"])
        return binds

    def _known_action(self, label: str, where: str) -> None:
        if label not in self.catalog.action_descs:
            raise _unknown_label(label, self.catalog, "action", where)
        if label not in self.considered:
            raise TargetFileError(
                f"{where}: pack {pack_of(label)!r} is not in the target file; list a capability of that pack"
            )

    def _fillable(self, scope_name: str, label: str) -> bool:
        bound = self.binds.get((scope_name, label), {})
        for need in self.catalog.action_descs[label].uses:
            if need.slot in bound:
                continue
            offering = [
                r
                for r, factory in self.roles[scope_name].items()
                if self.catalog.factories[factory].contract == need.contract
            ]
            if len(offering) != 1:
                return False
        return True

    # -- choosing ----------------------------------------------------------------------------------------

    def choose(self, scope_name: str, token: str) -> str | None:
        """The action that makes `token` true in the scope: `by:`, else the one candidate; None when no listed
        action makes it. Raises when several candidates remain."""
        labels = self.by_token.get(token, [])
        if token not in self.multi:
            return labels[0] if labels else None
        key = (scope_name, token)
        if key in self.pins:
            return self.pins[key]
        candidates = [l for l in labels if self._fillable(scope_name, l)]
        if len(candidates) == 1:
            self.chosen[key] = candidates[0]
            return candidates[0]
        where = "" if scope_name == ROOT else f" in scope {scope_name}"
        if not candidates:
            raise TargetFileError(
                f"state {token!r}{where} can be made true by {' or '.join(labels)}, but none of them has all its "
                "slots filled there; list the capability a slot needs, or name the role under `actions:`"
            )
        return self._ambiguous(token, where, candidates)

    @staticmethod
    def _ambiguous(token: str, where: str, candidates: list):
        raise TargetFileError(
            f"state {token!r}{where} can be made true by {' or '.join(candidates)}; say which with\n"
            f"    - state: {token}\n      by: <one of: {', '.join(candidates)}>"
        )

    def _pin_goals(self) -> set:
        init = set()
        for scope_name, scope in self.scopes.items():
            states = []
            for goal in scope["goals"]:
                states.append(goal["state"])
                if goal.get("by") is not None:
                    self._pin(scope_name, goal)
            if states:
                init.add(GoalClaim(scope=scope_name, states=frozenset(states), origin=TARGET_FILE_ORIGIN))
        return init

    def _pin(self, scope_name: str, goal: Mapping) -> None:
        by, state = goal["by"], goal["state"]
        where = f"{_shown(scope_name)}goal {state!r}"
        if by not in self.catalog.action_descs:
            raise _unknown_label(by, self.catalog, "action", where)
        if by not in self.considered:
            raise TargetFileError(
                f"{where}: by {by!r}, but pack {pack_of(by)!r} is not in the target file; list a capability of that pack"
            )
        if by not in self.by_token.get(state, ()):
            raise TargetFileError(
                f"{where}: {by} does not make it true; "
                f"candidates: {', '.join(self.by_token.get(state, ())) or '(none listed)'}"
            )
        self.pins[(scope_name, state)] = by

    def _walk(self) -> None:
        """Choose an action for every state each scope reaches from its goals."""
        for scope_name, scope in self.scopes.items():
            seen: set = set()
            work = [(scope_name, g["state"]) for g in scope["goals"]]
            while work:
                where, token = work.pop()
                if (where, token) in seen or (where == ROOT and token in self.assumed):
                    continue
                seen.add((where, token))
                work += self._requirements(where, self.choose(where, token))

    def _requirements(self, where: str, label: str | None) -> list:
        """(scope, state) pairs the action `label` needs first, when it runs in `where`."""
        refs = [ref for claim in self.catalog.action_claims[label] for ref in claim.requires] if label else []
        return [((ref.rpartition(":")[0] or where), ref.rpartition(":")[2]) for ref in refs]

    # -- claims ------------------------------------------------------------------------------------------

    def _override(self, scope_name: str, token: str, label: str) -> StateContractClaim:
        """This scope's claim for `token` from action `label`, with what the target file adds so far."""
        key = (scope_name, token)
        if key not in self.overrides:
            claims = self.catalog.action_claims[label]
            base = next((c for c in claims if c.token == token), claims[0])
            self.overrides[key] = dataclasses.replace(base, token=token, scope=scope_name, origin=TARGET_FILE_ORIGIN)
        return self.overrides[key]

    def claims(self):
        init = self._pin_goals()
        self._walk()
        for (scope_name, token), label in sorted({**self.chosen, **self.pins}.items()):
            self._override(scope_name, token, label)
        self._apply_relations()
        self._apply_binds()
        init.update(self.overrides.values())
        for label in self.considered:
            for claim in self.catalog.action_claims[label]:
                if claim.token not in self.multi:
                    init.add(claim)
        for item in self.doc["assume"]:
            init.add(
                AssumeClaim(
                    scope=ROOT,
                    token=item["state"],
                    owner=item.get("owner", ""),
                    reason=item.get("reason", ""),
                    origin=TARGET_FILE_ORIGIN,
                )
            )
        return init, dict(self.pins)

    def _apply_binds(self) -> None:
        for (scope_name, label), bind in self.binds.items():
            for claim in self.catalog.action_claims[label]:
                token = claim.token
                if token in self.multi and {**self.chosen, **self.pins}.get((scope_name, token)) != label:
                    continue  # another action makes this state in this scope
                base = self._override(scope_name, token, label)
                self.overrides[(scope_name, token)] = dataclasses.replace(base, bind=tuple(sorted(bind.items())))

    def _made_or_assumed(self, ref: str, scope_name: str, where: str) -> str:
        """The token of a state a relation names: it must be made by a listed action or assumed."""
        scope, _, token = state_ref(ref).rpartition(":")
        if token in self.by_token or (token in self.assumed and (scope or scope_name) == ROOT):
            return token
        listed = sorted({*self.by_token, *self.assumed})
        raise TargetFileError(
            f"{_shown(scope_name)}{where}: no listed action makes {token!r} true and it is not assumed; "
            f"states the listed packs make: {', '.join(listed) or '(none)'}"
        )

    def _apply_relations(self) -> None:
        """Add each relation's `after` and `breaks` to the claim of the action that makes its `state` true."""
        for scope_name, scope in self.scopes.items():
            for relation in scope["relations"]:
                state = relation["state"]
                where = f"relation of {state!r}"
                token = self._made_or_assumed(state, scope_name, where)
                for ref in (*relation["after"], *relation["breaks"]):
                    self._made_or_assumed(ref, scope_name, where)
                label = self._relation_action(scope_name, token, where)
                claims = self.catalog.action_claims[label]
                if (scope_name, token) not in self.overrides and not any(c.token == token for c in claims):
                    raise TargetFileError(
                        f"{_shown(scope_name)}{where}: {label} makes {token!r} as a side effect of another state; "
                        "put the relation on the state it makes first"
                    )
                base = self._override(scope_name, token, label)
                self.overrides[(scope_name, token)] = dataclasses.replace(
                    base,
                    requires=base.requires | frozenset(state_ref(r) for r in relation["after"]),
                    invalidates=base.invalidates | frozenset(state_ref(r) for r in relation["breaks"]),
                )

    def _relation_action(self, scope_name: str, token: str, where: str) -> str:
        labels = self.by_token.get(token, [])
        if not labels:
            raise TargetFileError(
                f"{_shown(scope_name)}{where}: {token!r} is only assumed, so no action runs to be ordered; "
                "put the relation on the action that needs it"
            )
        pinned = self.pins.get((scope_name, token))
        if pinned is not None:
            return pinned
        if len(labels) > 1:
            raise TargetFileError(
                f"{_shown(scope_name)}{where}: {token!r} can be made true by {' or '.join(labels)}; choose one with\n"
                f"    goals:\n      - state: {token}\n        by: <one of: {', '.join(labels)}>"
            )
        return labels[0]
