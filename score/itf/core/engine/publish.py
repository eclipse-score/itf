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
"""`@capability` and `@state`: how a pack (or a project) declares what it can contribute to a target.

A **capability factory** fulfils a capability contract:

    @capability("exec.command")                    # label: <pack>.<function name>, or label=
    def exec(shell: Shell) -> SshExec: ...         # `shell` is a slot: contract and shape from its annotation

An **action function** makes a state contract true. `after=` and `breaks=` name only states the action itself
depends on or ends; orderings between packs belong to the target file (`relations:`):

    @state("shell.open", also=("network.reachable",))
    def open_session(shell: Shell) -> None: ...
    @open_session.probe
    def is_open(shell: Shell) -> bool: ...

A slot is a parameter. Its annotation is a class (the consumer's own Protocol, never shared code) with a
`__contract__` attribute naming the contract; the annotation's members are the shape it expects. A parameter
`config` annotated with a dataclass is the settings schema. Any other parameter is an error naming it. What a
factory publishes is its return annotation (a class, often the factory's own Protocol). The label is `<pack>.<label or function name>`;
the pack is the `name` of the `pack.yaml` above the module, else `local` (the project's policy). A duplicate label is an error when
the parts are published.
`@major` after a contract name says which major a factory offers (or a slot expects); when both sides give one
they must agree.
"""

from __future__ import annotations

import collections.abc
import dataclasses
import inspect
import typing
from dataclasses import dataclass, field

from ..octo import Need, ProviderClaim, Shape, ShapeExpectationClaim, StateContractClaim, shape_of
from .config import ConfigSchema
from .metadata import metadata_of_file, pack_name
from .scopes import state_ref

PART_ATTR = "__itf_part__"  # on a decorated function: its descriptor


def split_major(text: str) -> tuple[str, int | None]:
    """`name@N` -> (name, N); a name without a valid major is returned whole."""
    base, at, major = text.partition("@")
    return (base, int(major)) if at and major.isdigit() and int(major) >= 1 else (text, None)


class DuplicateLabel(ValueError):
    """Two factories (or two actions) have the same label."""


def _annotations(func) -> dict:
    try:
        return typing.get_type_hints(func)
    except Exception:  # noqa: BLE001 - a forward reference that cannot resolve; report per parameter below
        return {k: v for k, v in getattr(func, "__annotations__", {}).items()}


def _shape(ann, *, signatures: bool = False) -> Shape:
    if not inspect.isclass(ann) or ann.__module__ == "builtins":
        return Shape()
    found = shape_of(ann, signatures=signatures)
    return Shape(members=frozenset(m for m in found.members if not m.name.startswith("_")), protocols=found.protocols)


def _yielded(ann):
    """`Iterator[X]` / `Generator[X, ...]` / `Iterable[X]` -> X, for fixture-style factories."""
    if typing.get_origin(ann) in (collections.abc.Iterator, collections.abc.Generator, collections.abc.Iterable):
        args = typing.get_args(ann)
        return args[0] if args else None
    return ann


def _label(func, label: str | None) -> tuple[str, str]:
    pack = pack_name(metadata_of_file(func.__globals__.get("__file__")))
    return pack, f"{pack}.{label or func.__name__}"


def _slots(func, what: str, label: str) -> tuple[tuple[Need, ...], dict, ConfigSchema | None]:
    """The needs (one per slot parameter), their declared majors and the config schema of `func`."""
    hints = _annotations(func)
    needs, majors, schema = [], {}, None
    for name in inspect.signature(func).parameters:
        ann = hints.get(name)
        if name == "config":
            if inspect.isclass(ann) and dataclasses.is_dataclass(ann):
                schema = ConfigSchema.from_dataclass(ann)
                continue
            raise TypeError(
                f"{what} {label}: parameter 'config' must be annotated with a dataclass (its fields are the "
                "settings a target file gives under `with:`); add `config: <YourSettings>`"
            )
        contract = getattr(ann, "__contract__", None) if inspect.isclass(ann) else None
        if not isinstance(contract, str):
            raise TypeError(
                f"{what} {label}: parameter {name!r} is neither a slot nor the config: annotate it with a class "
                f'that sets __contract__ (a Protocol with `__contract__ = "<contract>"` and the members this '
                f"{what} uses), or, for settings, name it 'config' and annotate it with a dataclass"
            )
        base, major = split_major(contract)
        needs.append(Need(slot=name, contract=base, expected=_shape(ann)))
        if major is not None:
            majors[name] = major
    return tuple(sorted(needs, key=lambda n: n.slot)), majors, schema


@dataclass
class FactoryDescriptor:
    label: str
    pack: str
    contract: str
    major: int | None
    gives: Shape
    needs: tuple[Need, ...]
    need_majors: dict
    impl: str
    module: str
    config_schema: ConfigSchema | None = None
    has_teardown: bool = False  # a generator: code after `yield` runs when the node is dismantled
    observes: object = False  # True, or a function of the settings: see `capability`

    def observable(self, config: dict) -> bool:
        """Can a later process, building this factory from `config`, see what an earlier one created?"""
        return bool(self.observes(config) if callable(self.observes) else self.observes)


@dataclass
class ActionDescriptor:
    label: str
    pack: str
    state: str
    impl: str
    module: str
    probe: str = ""
    after: tuple[str, ...] = ()
    breaks: tuple[str, ...] = ()
    also: tuple[str, ...] = ()
    uses: tuple[Need, ...] = ()
    need_majors: dict = field(default_factory=dict)
    extra_probes: dict[str, str] = field(default_factory=dict)
    config_schema: ConfigSchema | None = None


def _as_tuple(value, what: str) -> tuple[str, ...]:
    if isinstance(value, str):
        raise TypeError(f"{what} is a tuple of state names, not the string {value!r}")
    return tuple(value)


def capability(contract: str, *, label: str | None = None, observes=False, sensitive: bool = False):
    """Declare a capability factory: fulfils `contract` (`"exec.command"`, or `"exec.command@1"`).

    `observes` is the opt-in that lets a target be left running (`itf up --detach`) and taken down by a later
    process (`itf down`): True says that a factory built afresh from the same settings sees what an earlier
    one created (a container found by its labels), so its probes tell the truth and its teardown removes it. It
    may be a function of the settings (a dict) when that holds only for some of them. A factory with a teardown
    (a generator) that does not say so makes such a target refused.

    `sensitive` makes every setting of this factory a secret (a login, a token): redacted in every plan and report,
    and masked in logs while a session runs. A single field is marked with `field(metadata={"sensitive": True})`."""
    base, major = split_major(contract)

    def deco(func):
        pack, full = _label(func, label)
        needs, majors, schema = _slots(func, "capability factory", full)
        if sensitive and schema is not None:
            schema = schema.all_sensitive()
        shape = _shape(_yielded(_annotations(func).get("return")), signatures=True)
        desc = FactoryDescriptor(
            label=full,
            pack=pack,
            contract=base,
            major=major,
            gives=shape,
            needs=needs,
            need_majors=majors,
            impl=f"{func.__module__}:{func.__qualname__}",
            module=func.__module__,
            config_schema=schema,
            has_teardown=inspect.isgeneratorfunction(func),
            observes=observes,
        )
        _attach(func, desc)
        return func

    return deco


def state(state_name: str, *, after=(), breaks=(), also=(), label: str | None = None):
    """Declare an action function: makes the state contract `state_name` true. `after` names states that must
    hold first, `breaks` states this action destroys, `also` further states it makes true in one go. Add
    `@<action>.probe` to observe whether the state holds."""
    after, breaks, also = (_as_tuple(v, n) for v, n in ((after, "after"), (breaks, "breaks"), (also, "also")))

    def deco(func):
        pack, full = _label(func, label)
        needs, majors, schema = _slots(func, "action", full)
        slot_names = {n.slot for n in needs}
        desc = ActionDescriptor(
            label=full,
            pack=pack,
            state=state_name,
            impl=f"{func.__module__}:{func.__qualname__}",
            module=func.__module__,
            after=after,
            breaks=breaks,
            also=also,
            uses=needs,
            need_majors=majors,
            config_schema=schema,
        )
        _attach(func, desc)

        def check_probe(probe_func):
            params = set(inspect.signature(probe_func).parameters) - {"config"}
            if params != slot_names:
                raise TypeError(
                    f"probe {probe_func.__qualname__!r}: parameters {sorted(params)} must be the action's slots "
                    f"{sorted(slot_names)} (plus optional 'config')"
                )

        def probe(probe_func):
            check_probe(probe_func)
            desc.probe = f"{probe_func.__module__}:{probe_func.__qualname__}"
            return probe_func

        def probe_for(other: str):
            if other not in desc.also:
                raise TypeError(
                    f"{full}: probe_for({other!r}) names a state the action does not list in also={desc.also}"
                )

            def register(probe_func):
                check_probe(probe_func)
                desc.extra_probes[other] = f"{probe_func.__module__}:{probe_func.__qualname__}"
                return probe_func

            return register

        func.probe = probe
        func.probe_for = probe_for
        return func

    return deco


def _attach(func, desc) -> None:
    """The descriptor travels with the function: whoever holds the function (a module's members) can read it."""
    setattr(func, PART_ATTR, desc)
    func.__itf_label__ = desc.label


def part_of(func) -> FactoryDescriptor | ActionDescriptor | None:
    """The descriptor `@capability` or `@state` attached to `func`, or None."""
    desc = getattr(func, PART_ATTR, None) if inspect.isfunction(func) else None
    return desc if isinstance(desc, (FactoryDescriptor, ActionDescriptor)) else None


def declared_parts(module) -> list:
    """The descriptors of the capability factories and actions `module` defines (not those it imported), in the
    order they appear in the module. Read from the module's own members: nothing is registered anywhere."""
    found: list = []
    for member in vars(module).values():
        desc = part_of(member)
        if desc is not None and desc.module == module.__name__ and not any(desc is seen for seen in found):
            found.append(desc)
    return found


def declared_expectations(module) -> tuple[ShapeExpectationClaim, ...]:
    value = getattr(module, "itf_expect", ())
    declarations = value if isinstance(value, (list, tuple)) else (value,)
    expectations = []
    for declaration in declarations:
        contract = getattr(declaration, "__contract__", None)
        if not getattr(declaration, "_is_protocol", False) or not isinstance(contract, str) or not contract:
            raise TypeError(f"{module.__name__}.itf_expect must contain Protocols with a nonempty __contract__")
        shape = _shape(declaration, signatures=True)
        if not shape.members:
            raise TypeError(f"{module.__name__}.itf_expect: {declaration.__name__} declares no public members")
        expectations.append(ShapeExpectationClaim(contract=contract, shape=shape, origin=module.__name__))
    return tuple(expectations)


@dataclass(frozen=True)
class Catalog:
    """What the registered modules declared: data only (names, shapes, schemas), no live objects."""

    providers: tuple[ProviderClaim, ...]
    actions: tuple[StateContractClaim, ...]
    factories: dict = field(default_factory=dict)  # label -> FactoryDescriptor
    action_descs: dict = field(default_factory=dict)  # label -> ActionDescriptor
    action_claims: dict = field(default_factory=dict)  # label -> tuple[StateContractClaim] (one per state it makes)
    config_schemas: dict[str, ConfigSchema] = field(default_factory=dict)  # label -> schema
    expectations: tuple[ShapeExpectationClaim, ...] = ()

    def factory(self, label: str) -> FactoryDescriptor:
        return self.factories[label]

    def offering(self, contract: str) -> tuple[str, ...]:
        """Labels of the factories fulfilling `contract`."""
        return tuple(sorted(l for l, f in self.factories.items() if f.contract == contract))

    def packs(self) -> tuple[str, ...]:
        return tuple(sorted({d.pack for d in (*self.factories.values(), *self.action_descs.values())}))


def _factory_claim(desc: FactoryDescriptor, origin: str) -> ProviderClaim:
    return ProviderClaim(
        name=desc.label,
        implements=desc.contract,
        gives=desc.gives,
        needs=desc.needs,
        impl=desc.impl,
        origin=origin,
    )


def _action_claims(desc: ActionDescriptor, origin: str) -> tuple:
    """One claim per state the action makes true: its own, then each state with a probe of its own."""
    claim = StateContractClaim(
        token=desc.state,
        impl=desc.impl,
        probe=desc.probe,
        requires=frozenset(state_ref(r) for r in desc.after),
        invalidates=frozenset(state_ref(r) for r in desc.breaks),
        also_delivers=frozenset(desc.also) - set(desc.extra_probes),
        uses=desc.uses,
        scope="",
        origin=origin,
    )
    others = [
        dataclasses.replace(claim, token=other, probe=probe, also_delivers=frozenset())
        for other, probe in sorted(desc.extra_probes.items())
    ]
    return (claim, *others)


def publish(registry) -> Catalog:
    """The parts the registered modules declare. Only what the session registered counts, so what a pack offers
    never depends on what else was imported, and a module that is imported again declares what it says now."""
    from .registry import contributor_of  # the registry imports this module

    providers, actions = [], []
    factories: dict[str, FactoryDescriptor] = {}
    action_descs: dict[str, ActionDescriptor] = {}
    action_claims: dict[str, tuple] = {}
    config_schemas: dict[str, ConfigSchema] = {}
    expectations = []
    for mod_name in sorted(registry.modules):
        origin = registry.origin_of_package(contributor_of(mod_name))
        if origin is None:
            continue
        expectations.extend(declared_expectations(registry.modules[mod_name]))
        for desc in declared_parts(registry.modules[mod_name]):
            if desc.config_schema is not None:
                config_schemas[desc.label] = desc.config_schema
            if isinstance(desc, FactoryDescriptor):
                taken = factories.get(desc.label)
                if taken is not None:
                    raise DuplicateLabel(f"two capability factories are {desc.label}: {taken.module} and {desc.module}")
                factories[desc.label] = desc
                providers.append(_factory_claim(desc, origin))
                continue
            taken = action_descs.get(desc.label)
            if taken is not None:
                raise DuplicateLabel(f"two actions are {desc.label}: {taken.module} and {desc.module}")
            action_descs[desc.label] = desc
            action_claims[desc.label] = _action_claims(desc, origin)
            actions.extend(action_claims[desc.label])
    return Catalog(
        providers=tuple(providers),
        actions=tuple(actions),
        factories=factories,
        action_descs=action_descs,
        action_claims=action_claims,
        config_schemas=config_schemas,
        expectations=tuple(expectations),
    )


def label_of(value) -> str | None:
    return getattr(value, "__itf_label__", None)
