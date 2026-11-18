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
"""Contributor metadata: the `pack.yaml` that sits next to a contributor's package.

Core uses the pack's `name` for labels and `version` for provenance reporting. Other fields belong to the tools
that read them. Code with no `pack.yaml` above it is the project's own, and its pack is `project`. Which contracts
a pack fulfils, and at which major, is not here: the `@capability`/`@state` decorators say it.
"""

from __future__ import annotations

import functools
import logging
import sys
from pathlib import Path

import yaml

from .yaml_text import safe_load as yaml_safe_load

METADATA_FILE = "pack.yaml"
logger = logging.getLogger("score.itf.core")


@functools.cache
def _read(directory: Path) -> dict | None:
    """The metadata in `directory` or the nearest parent of it holding the file that is still inside the package:
    the walk stops at the package root, the first directory without an `__init__.py` (itself included only when it
    holds the file). A project file under no package is read from its own directory only."""
    for candidate in (directory, *directory.parents):
        file = candidate / METADATA_FILE
        if file.is_file():
            try:
                data = yaml_safe_load(file.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as exc:
                logger.warning("contributor metadata %s is unreadable: %s", file, exc)
                return None
            return data if isinstance(data, dict) else None
        if not (candidate / "__init__.py").is_file():
            return None  # the package root is passed: what lies above belongs to somebody else
    return None


def metadata_of_file(file) -> dict | None:
    """The metadata of the contributor the source file `file` belongs to, or None."""
    return _read(Path(file).resolve().parent) if file else None


def contributor_metadata(module) -> dict | None:
    """The metadata of the contributor `module` (a module or its name) belongs to, or None."""
    if isinstance(module, str):
        module = sys.modules.get(module)
    return metadata_of_file(getattr(module, "__file__", None))


LOCAL_PACK = "local"


def pack_name(metadata: dict | None) -> str:
    """The pack's name: `name` in its `pack.yaml`; code outside any pack belongs to the pack `local`, which no pack may be named."""
    name = (metadata or {}).get("name")
    if name == LOCAL_PACK:
        raise ValueError(
            f"the pack name {LOCAL_PACK!r} is reserved for the project's policy (policy.py); rename the pack"
        )
    return name if isinstance(name, str) and name else LOCAL_PACK
