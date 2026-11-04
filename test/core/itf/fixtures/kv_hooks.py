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
"""Hooks of a project's policy: a readiness check and evidence at teardown."""

from score.itf.core import hookimpl


@hookimpl
def itf_verify(session):
    session.check("store.answers", session.target.store.get("seeded") is not None, detail="seeded")


@hookimpl
def itf_teardown(session):
    session.target.store.put("teardown", ", ".join(session.target.names()))
    session.target.store.put("evidence_dir", str(session.evidence_dir))
