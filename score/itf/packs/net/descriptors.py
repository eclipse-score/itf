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
"""Endpoint and credentials values, and the config schemas that build them."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int


@dataclass(frozen=True)
class Credentials:
    """A login. `key_path` names a private key file; key material never goes into a target file."""

    user: str
    password: str | None = field(default=None, metadata={"sensitive": True})
    key_path: str | None = field(default=None, metadata={"sensitive": True})


@dataclass(frozen=True)
class KeyCredentials:
    user: str
    key_path: str = field(metadata={"sensitive": True})


@dataclass(frozen=True)
class PasswordCredentials:
    user: str
    password: str = field(default="", metadata={"sensitive": True})
