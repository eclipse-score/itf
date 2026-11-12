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
"""A part with a secret in its configuration, for the run-directory tests."""

from dataclasses import dataclass, field

from score.itf.core import capability


@dataclass
class VaultConfig:
    user: str = "admin"
    password: str = field(default="", metadata={"sensitive": True})


class Vault:
    def __init__(self, config):
        self.config = config


@capability("kv.vault", label="vault")
def make_vault(config: VaultConfig) -> Vault:
    return Vault(config)
