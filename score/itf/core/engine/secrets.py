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
"""Collect marked setting values for redaction at ITF-owned output boundaries.

Config values in plans and artifacts are redacted structurally by their schema. Free-text replacement is
limited to ITF-generated diagnostics, assumptions, and explicitly designated error fields in reports/events.
It does not install global logging hooks or rewrite arbitrary component logs, exception objects, command
output, pytest output, or external artifacts. Short values are excluded from free-text matching to avoid
replacing common text; marked config fields are redacted regardless of value length.
"""

from __future__ import annotations

REDACTED = "[redacted]"
MIN_LENGTH = 6
_TEXT_FIELDS = frozenset({"detail", "error", "failure", "reason"})


class Secrets:
    """Replace known long values in explicitly selected ITF-owned text fields."""

    def __init__(self) -> None:
        self._values: set[str] = set()

    def add(self, value) -> None:
        if isinstance(value, (str, int, float)) and len(str(value)) >= MIN_LENGTH:
            self._values.add(str(value))

    def mask(self, text: str) -> str:
        return _replace(text, self._values)

    def mask_text_fields(self, value):
        """Mask only designated free-text fields in an ITF-owned structured report."""
        if isinstance(value, dict):
            return {
                key: self.mask(item) if key in _TEXT_FIELDS and isinstance(item, str) else self.mask_text_fields(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self.mask_text_fields(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.mask_text_fields(item) for item in value)
        return value


def _replace(text: str, values) -> str:
    """Replace long values first, but only at explicit ITF-owned text boundaries."""
    replacement = _replacement(values)
    for value in sorted(values, key=len, reverse=True):
        text = text.replace(value, replacement)
    return text


def _replacement(values) -> str:
    return next(
        candidate for candidate in (REDACTED, "***", "###", "") if all(value not in candidate for value in values)
    )
