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
"""A capability with a sensitive setting and an action that reports it in an error."""

from dataclasses import dataclass, field
from typing import Protocol

from score.itf.core import capability, state


@dataclass
class TokenConfig:
    value: str = field(default="", metadata={"sensitive": True})
    label: str = "public"


class Token:
    value: str

    def __init__(self, config: TokenConfig):
        self.value = config["value"]


class TokenLike(Protocol):
    __contract__ = "kv.token"
    value: str


@capability("kv.token", label="token")
def make_token(config: TokenConfig) -> Token:
    return Token(config)


@state("kv.logged_in", label="log_in")
def log_in(token: TokenLike) -> None:
    raise RuntimeError(f"the server refused {token.value}")


@log_in.probe
def logged_in(token: TokenLike) -> bool:
    return False
