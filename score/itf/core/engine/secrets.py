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
"""Secrets ITF must never show. The values of sensitive settings (a settings field marked `sensitive`, or every
setting of a `@capability(..., sensitive=True)`) are collected when a plan is made; while the session runs, every log
record is masked whichever handler prints it, and ITF masks its failure reports, evidence and pytest's failure
output with the same values.

A value shorter than MIN_LENGTH is not masked: hiding a short word everywhere would also hide it in names and
paths (`score` in `score.itf`). Such values are still redacted wherever ITF shows settings.
"""

from __future__ import annotations

import logging

REDACTED = "[redacted]"
MIN_LENGTH = 6

_active: list[Secrets] = []
_factory = None


class Secrets:
    def __init__(self) -> None:
        self._values: set[str] = set()

    def add(self, value) -> None:
        if isinstance(value, str) and len(value) >= MIN_LENGTH:
            self._values.add(value)

    def mask(self, text: str) -> str:
        return _replace(text, self._values)

    def install(self) -> None:
        """Mask every log record made from now on, until `uninstall`."""
        global _factory
        if self in _active:
            return
        if not _active:
            _factory = logging.getLogRecordFactory()
            logging.setLogRecordFactory(_masked_record)
        _active.append(self)

    def uninstall(self) -> None:
        global _factory
        if self in _active:
            _active.remove(self)
        if not _active and _factory is not None:
            logging.setLogRecordFactory(_factory)
            _factory = None


def mask(text: str) -> str:
    """`text` with the secrets of every running session masked."""
    return _replace(text, {value for secrets in _active for value in secrets._values})


def _replace(text: str, values) -> str:
    """Longest first, so a secret that contains another is masked whole."""
    for value in sorted(values, key=len, reverse=True):
        text = text.replace(value, REDACTED)
    return text


def _masked_record(*args, **kwargs):
    record = _factory(*args, **kwargs)
    try:
        message = record.getMessage()
    except Exception:  # noqa: BLE001 - a malformed record is logging's problem, not a reason to drop it
        return record
    masked = mask(message)
    if masked != message:
        record.msg, record.args = masked, ()
    return record
