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
"""YAML reading for every ITF file: the safe loader, in C when PyYAML was built with libyaml (about ten times
faster on a target file), else in Python. Both accept the same documents."""

import yaml

_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def safe_load(text):
    """`yaml.safe_load`, with the fastest safe loader available."""
    return yaml.load(text, Loader=_LOADER)  # noqa: S506 - a safe loader, never the full one
