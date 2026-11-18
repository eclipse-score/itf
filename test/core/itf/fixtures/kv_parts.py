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
"""Project parts for the engine tests: an in-memory store, a view over it, two ways to seed it."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from score.itf.core import capability, state

EVENTS: list[str] = []


class MemoryStore:
    def __init__(self, name: str):
        self.name = name
        self.data: dict = {}

    def get(self, key):
        return self.data.get(key)

    def put(self, key, value):
        self.data[key] = value


class View:
    def __init__(self, store):
        self.store = store

    def read(self, key):
        return self.store.get(key)


@dataclass
class StoreConfig:
    name: str = "mem"
    size: int = 8


class Store(Protocol):
    __contract__ = "kv.store"

    def get(self, key): ...
    def put(self, key, value): ...


@capability("kv.store", label="store")
def make_store(config: StoreConfig) -> Iterator[MemoryStore]:
    store = MemoryStore(config["name"] if "name" in config else "mem")
    EVENTS.append("store built")
    yield store
    EVENTS.append("store closed")


@capability("kv.view", label="view")
def make_view(store: Store) -> View:
    return View(store)


class Slim:
    """A view without `read`: the role exists, the member does not."""

    def peek(self, key):
        return None


@capability("kv.view@1", label="view_v1")
def make_view_v1(store: Store) -> View:
    return View(store)


@capability("kv.view", label="slim_view")
def make_slim_view(store: Store) -> Slim:
    return Slim()


@state("kv.seeded", label="seed_a")
def seed_a(store: Store) -> None:
    EVENTS.append("seed_a")
    store.put("seeded", "a")


@seed_a.probe
def seeded_a(store: Store) -> bool:
    return store.get("seeded") is not None


@state("kv.seeded", label="seed_b")
def seed_b(store: Store) -> None:
    EVENTS.append("seed_b")
    store.put("seeded", "b")


@seed_b.probe
def seeded_b(store: Store) -> bool:
    return store.get("seeded") is not None


@state("kv.ready", after=("kv.seeded",), label="ready")
def ready(store: Store) -> None:
    EVENTS.append("ready")


@ready.probe
def is_ready(store: Store) -> bool:
    return "ready" in EVENTS


@state("kv.broken", label="broken")
def broken(store: Store) -> None:
    raise RuntimeError("the store refused")


@state("kv.audited", label="audit")
def audit(store: Store) -> None:
    EVENTS.append("audit")


@capability("kv.cache", label="cache", observes=True)
def make_cache() -> Iterator[object]:
    yield object()


@capability("kv.memo", label="memo", observes=lambda config: "dir" in config)
def make_memo() -> Iterator[object]:
    yield object()


@capability("kv.plain", label="plain")
def make_plain() -> object:
    return object()
