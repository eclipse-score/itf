<!--
*******************************************************************************
Copyright (c) 2026 Contributors to the Eclipse Foundation

See the NOTICE file(s) distributed with this work for additional
information regarding copyright ownership.

This program and the accompanying materials are made available under the
terms of the Apache License Version 2.0 which is available at
https://www.apache.org/licenses/LICENSE-2.0

SPDX-License-Identifier: Apache-2.0
*******************************************************************************
-->

# DR-001-Infra: Unit Test Infrastructure Design

**Date:** 2026-05-11
**Status:** Accepted
**PR:** [eclipse-score/itf#94](https://github.com/eclipse-score/itf/pull/94)
**Discussion:** [eclipse-score/discussions#2867](https://github.com/orgs/eclipse-score/discussions/2867)

> This record follows the Decision Record convention established by the
> Eclipse S-CORE project:
> [eclipse-score/score — docs/design_decisions](https://github.com/eclipse-score/score/tree/main/docs/design_decisions).

## Overview

This decision record documents the infrastructure design for unit testing in
ITF. It covers the Bazel macro, dependency scoping strategy, pytest bootstrap
pattern, and mocking library choice, all accepted as part of PR #94.

## Problem Statement

ITF previously had only integration tests: tests that start a real target
(Docker or QEMU) and exercise the system end-to-end. Adding unit tests raised
four concrete questions that each had multiple viable answers:

1. Should unit tests reuse `py_itf_test` or have a dedicated macro?
2. How should Bazel dependencies be scoped to keep tests atomic?
3. How does pytest run inside Bazel, and what does that mean for test
   structure?
4. Which mocking library should be used?

## Options Evaluated

### Macro design

**Option A — Reuse `py_itf_test` with empty `plugins`.**
The macro would not crash with an empty plugin list, but it would still
generate the launcher script and resolve `PyItfPluginInfo` providers. The
BUILD file would not communicate that no target is involved.

**Option B — Dedicated `py_itf_unittest` macro (chosen).**
A thin wrapper around `py_test` with no plugin machinery. The name makes
intent explicit. `pytest-mock` is included as a default dep. JUnit XML
reporting is baked in via `$XML_OUTPUT_FILE`.

### Dependency scoping

**Option A — One large Bazel target per package.**
Simple to maintain, but pulls in all transitive dependencies as runfiles.
Bazel measures coverage over all files in the runfiles tree, so the coverage
denominator grows with every transitive dep, even ones not under test.

**Option B — Surgical target splitting (chosen).**
Split Bazel targets along cohesion boundaries so each unit test can declare
only the module it actually exercises. Example: `score/itf/plugins/qemu/BUILD`
was split into `:config` (Pydantic schema only) and `:qemu` (full plugin). The
unit test for schema validation depends only on `:config`, excluding process
management, SSH, and QEMU binary wrappers from its runfiles tree.

### Pytest bootstrap

**Option A — `score_py_pytest` from `@score_tooling`.**
The tooling repository provides a `score_py_pytest` rule, but it bundles a
full Python development environment including `basedpyright` and
`nodejs-wheel-binaries`. These are unrelated to the code under test and expand
the runfiles tree significantly, inflating the coverage denominator and
increasing build time.

**Option B — Shared `main.py` entry point (chosen).**
`py_test` requires an executable Python module. A minimal `main.py` that calls
`pytest.main(sys.argv[1:])` is the de facto standard for Bazel + pytest. The
same bootstrap file is shared across integration and unit test rules, keeping
the approach consistent. This was confirmed as the community standard in the
GitHub discussion linked above.

### Mocking library

**Option A — `unittest.mock.patch` via context managers.**
Part of the standard library, no extra dep. Context manager nesting becomes
verbose when multiple objects need patching.

**Option B — `pytest-mock` via the `mocker` fixture (chosen).**
Patches are registered and torn down automatically through the pytest fixture
lifecycle, removing context manager nesting. Cleaner for tests that mock
several collaborators:

```python
def test_ping_reachable(mocker):
    mocker.patch("score.itf.core.com.ping.shutil.which", return_value="/usr/bin/ping")
    mocker.patch("score.itf.core.com.ping.os.system", return_value=0)
    assert ping("127.0.0.1") is True
```

## Decision & Rationale

All four decisions favour the option that minimises coupling and maximises
clarity in the BUILD file:

- **Dedicated `py_itf_unittest` macro** — the name signals "no target" and
  the macro carries no plugin machinery.
- **Surgical Bazel target splitting** — dep declarations in BUILD files become
  a lightweight design signal: a test that can only list `:config` as a dep
  proves that the schema module is cohesive and has no hidden coupling.
- **Shared `main.py` bootstrap** — consistent with integration tests and
  aligned with community practice.
- **`pytest-mock`** — included as a default dep in `py_itf_unittest`; test
  authors get `mocker` without an explicit declaration.

Coverage uses Bazel-native LCOV (`configure_coverage_tool = True` in
`MODULE.bazel`) rather than `pytest-cov`, for consistency across all test
types and compatibility with Bazel's `--combined_report`.

## Key Implications

- Unit tests live in `test/unit/` and integration tests in `test/integration/`.
  The split is enforced by directory layout and BUILD files, not just naming.
- Adding unit tests for a new module may require splitting its Bazel target if
  the current target has a large transitive dep set. This is intentional:
  splitting is a design signal that the module has a cohesion opportunity.
- `py_itf_unittest` does not support the `plugins` attribute. A test that
  needs a real target belongs in `test/integration/` and uses `py_itf_test`.
- The `mocker` fixture preference applies project-wide; `unittest.mock` context
  managers should not be introduced in new tests.
