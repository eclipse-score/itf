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
"""Two actions making one state, one of which needs a slot a target file may leave unfilled."""

from typing import Protocol

from score.itf.core import capability, state


EVENTS: list[str] = []


class Store(Protocol):
    __contract__ = "kv.store"

    def get(self, key): ...
    def put(self, key, value): ...


class Lookup:
    def lookup(self, key):
        return None


class Index(Protocol):
    __contract__ = "kv.index"

    def lookup(self, key): ...


@capability("kv.index", label="index")
def make_index() -> Lookup:
    return Lookup()


@state("kv.indexed", label="index_with_lookup")
def index_with_lookup(store: Store, index: Index) -> None:
    EVENTS.append("index_with_lookup")


@state("kv.indexed", label="index_plain")
def index_plain(store: Store) -> None:
    EVENTS.append("index_plain")
