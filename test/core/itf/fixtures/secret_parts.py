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
"""A capability whose every setting is a secret, and an action that leaks one into its error, for the tests that
check ITF never shows a secret."""

from dataclasses import dataclass
from typing import Protocol

from score.itf.core import capability, state


@dataclass
class TokenConfig:
    value: str = ""


class Token:
    value: str

    def __init__(self, config: TokenConfig):
        self.value = config["value"]


class TokenLike(Protocol):
    __contract__ = "kv.token"
    value: str


@capability("kv.token", label="token", sensitive=True)
def make_token(config: TokenConfig) -> Token:
    return Token(config)


@state("kv.logged_in", label="log_in")
def log_in(token: TokenLike) -> None:
    raise RuntimeError(f"the server refused {token.value}")


@log_in.probe
def logged_in(token: TokenLike) -> bool:
    return False
