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
"""Static descriptor providers: where a service listens and how to log in."""

from score.itf.core import capability

from .descriptors import Credentials, Endpoint, KeyCredentials, PasswordCredentials


@capability("descriptor.endpoint", label="endpoint")
def static_endpoint(config: Endpoint) -> Endpoint:
    return Endpoint(config["host"], config["port"])


@capability("descriptor.credentials", label="key")
def key_credentials(config: KeyCredentials) -> Credentials:
    return Credentials(config["user"], key_path=config["key_path"])


@capability("descriptor.credentials", label="password")
def password_credentials(config: PasswordCredentials) -> Credentials:
    """An empty password is a valid login on many images (e.g. root on a development build)."""
    return Credentials(config["user"], password=config.get("password", ""))
