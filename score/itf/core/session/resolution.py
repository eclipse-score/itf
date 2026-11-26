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
"""Resolution: from a target file to the two plans, before anything is built.

Gate 1 decides what must exist (which factory fills which role: the target plan); gate 2 decides what must happen
on it (the ordered actions that make the goals true: the action plan). Between the gates the plan is checked:
policy expectations, contract majors, and every role's settings against its factory's schema. Nothing here probes
or constructs, so resolution is safe without hardware (`--itf-plan`, collection, `itf_target` at build time).

Results are filled in step by step, so a resolution that fails half-way still shows what it found.
"""

from __future__ import annotations

import dataclasses
import logging

from .. import gating, octo
from ..engine import packs as pack_loader
from ..engine.config import sensitive_values
from ..engine.log import describe_packs, log_config_issues, log_packs, log_resolution, log_target_summary
from ..engine.metadata import LOCAL_PACK
from ..engine.publish import publish, split_major
from ..engine.registry import ORIGINS, expand, register_modules
from ..engine.render import render
from ..engine.scopes import ROOT, display
from ..frontends import target_file
from ..target_handle import name_clashes
from .errors import ConfigValidationFailed, ResolutionFailed, TargetNameClash
from .record import RunRecord

PRECEDENCE = ORIGINS


def follow_roots(roots) -> list:
    """Without pytest: `roots` are the project's policy; their `pytest_plugins` are followed as pytest would."""
    from ..engine.registry import follow

    return list(follow((r, "policy") for r in roots))


def log_target_file(source, overrides) -> None:
    logging.getLogger("score.itf.core").info(
        "target file: %s%s",
        source.describe(),
        "".join(f"; override {o.describe()}" for o in overrides),
    )


class Resolution:
    """What resolving a target file found. Read after `Session.resolve()`; fields stay None up to the step that
    failed."""

    def __init__(self, record: RunRecord):
        self.record = record
        self.document: dict | None = None  # the target file, overrides merged
        self.packs: list = []  # (name, version, module) of each pack the target file loaded
        self.registry = None  # the registered packs and project modules
        self.catalog = None  # what they declare, as data
        self.factory_majors: dict = {}  # factory label -> the major it offers (absent: unknown)
        self.compiled = None  # the target file compiled against the catalog
        self.setup_claims: frozenset = frozenset()  # gate 1's input
        self.init_claims: frozenset = frozenset()  # gate 2's input
        self.target_plan = None  # gate 1's plan
        self.scopes: frozenset = frozenset()  # the device scopes beside the root
        self.action_plan = None  # gate 2's plan with nothing observed: every action the goals need

    # ---- steps, in order ----

    def load(self, source, overrides) -> None:
        self.document = target_file.load_all(source, overrides) if source else target_file.load({})
        if source is not None:
            log_target_file(source, overrides)

    def declare_parts(self, contributors, roots) -> None:
        """Load the packs the target file names, register them with the project's code, publish what they
        declare. `contributors` are (module, origin) pairs a runner already loaded; else `roots` are the policy."""
        from ..frontends.target_source import load_policies

        doc = self.document
        modules = target_file.pack_modules(doc)
        pack_entries = [pack_loader.load(name, modules) for name in target_file.packs_of(doc) if name != LOCAL_PACK]
        project = expand(contributors) if contributors is not None else follow_roots(roots)
        project = [*project, *follow_roots(load_policies(doc["policies"]))]
        self.packs = describe_packs(pack_entries)
        log_packs(self.packs)
        self.registry = register_modules([*expand(pack_entries), *project])
        self.catalog = publish(self.registry)
        self.factory_majors = {l: f.major for l, f in self.catalog.factories.items() if f.major is not None}

    def plan_roles(self, *, placeholders: bool, definitions: dict) -> None:
        """Gate 1, then what is checked on its plan before anything else relies on it."""
        compiled = target_file.compile(self.document, self.catalog, placeholders=placeholders)
        self.compiled = compiled
        self.setup_claims = compiled.setup | frozenset(self.catalog.providers)
        self.init_claims = compiled.init
        result = octo.resolve_target(self.setup_claims, precedence=PRECEDENCE)
        if not result.ok():
            self.fail(1, "capabilities", result.diagnostics)
        plan = self.target_plan = result.plan
        self._check_policy_expectations(plan)
        self._check_majors(plan)
        log_resolution(1, "capabilities", True, ())
        log_target_summary(plan)
        self.record.warn(gating.deprecations(plan, definitions))
        self._check_settings(plan)
        self.scopes = frozenset(s for s in compiled.roles if s != ROOT)
        # `target.<x>` must mean one thing: a role named like a scope or a handle member would be
        # ambiguous, so it is rejected up front instead of resolving to whichever wins.
        clashes = name_clashes(plan, self.scopes)
        if clashes:
            raise TargetNameClash(clashes)

    def plan_actions(self) -> None:
        """Gate 2 with nothing observed: every action the goals need."""
        self.action_plan = self.plan(self.init_claims)
        log_resolution(2, "states", True, ())

    # ---- used again at run time ----

    def plan(self, claims, *, observed: frozenset = frozenset(), assumed: frozenset = frozenset()):
        """Gate 2 for `claims`, skipping what `observed` says holds and what `assumed` takes on faith."""
        result = octo.resolve_actions(
            claims, self.target_plan, precedence=PRECEDENCE, observed_states=observed, assumed_states=assumed
        )
        if not result.ok():
            self.fail(2, "states", result.diagnostics)
        return result.plan

    def fail(self, gate: int, phase: str, diagnostics) -> None:
        roles = self.compiled.roles if self.compiled is not None else {}
        text = render(diagnostics, gate=gate, phase=phase, catalog=self.catalog, roles=roles)
        exc = ResolutionFailed(gate, phase, diagnostics, text)
        self.record.resolution_failure = exc
        log_resolution(gate, phase, False, diagnostics)
        raise exc

    # ---- checks between the gates ----

    def _check_settings(self, plan) -> None:
        """Settings are validated against each factory's schema here, between the gates, so a typo in a
        target file fails at plan time with the role named, not when the factory is first used."""
        issues = []
        for node in plan.nodes:
            schema = self.catalog.config_schemas.get(node.provider)
            if schema is not None:
                issues.extend((node.ref, node.provider, message) for message in schema.validate(dict(node.config)))
        self.record.config_issues = tuple(issues)
        for value in sensitive_values(plan, self.catalog.config_schemas):
            self.record.secrets.add(value)
        if issues:
            log_config_issues(issues)
            raise ConfigValidationFailed(issues)

    def _check_policy_expectations(self, plan) -> None:
        catalog = self.catalog
        diagnostics = []
        unknown = []
        for expectation in catalog.expectations:
            contract, major = split_major(expectation.contract)
            for node in plan.nodes:
                if node.contract != contract:
                    continue
                offered = catalog.factories[node.provider].major
                if major is not None:
                    if offered is None:
                        unknown.append(
                            f"{expectation.origin}: {display(node.ref)} ({node.provider}) has no declared major; "
                            f"policy requires {expectation.contract}"
                        )
                        continue
                    if offered != major:
                        continue
                diagnostics.extend(
                    dataclasses.replace(
                        diagnostic,
                        evidence=tuple(
                            sorted(
                                (
                                    *diagnostic.evidence,
                                    ("policy", expectation.origin),
                                    ("contract", expectation.contract),
                                )
                            )
                        ),
                    )
                    for diagnostic in octo.shape_mismatches(node.ref, node.gives, expectation.shape, gate=1)
                )
        if unknown:
            message = "policy contract major unknown:\n  " + "\n  ".join(unknown)
            if diagnostics:
                message += "\n" + render(
                    diagnostics,
                    gate=1,
                    phase="policy expectations",
                    catalog=catalog,
                    roles=self.compiled.roles,
                )
            raise target_file.TargetFileError(message)
        if diagnostics:
            self.fail(1, "policy expectations", tuple(diagnostics))

    def _check_majors(self, plan) -> None:
        """When a factory offers `@major` and a slot expects one, they must agree."""
        catalog = self.catalog
        problems = []
        for node in plan.nodes:
            expected = catalog.factories[node.provider].need_majors
            for slot, ref in node.bindings:
                provider = plan.node(ref).provider
                offered = catalog.factories[provider].major
                if slot in expected and offered is not None and expected[slot] != offered:
                    problems.append(
                        f"{display(node.ref)} ({node.provider}) expects its {slot} at @{expected[slot]} but "
                        f"{display(ref)} ({provider}) offers @{offered}"
                    )
        if problems:
            raise target_file.TargetFileError("contract major mismatch:\n  " + "\n  ".join(problems))
