..
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
.. _itf_architecture:

Architecture
============

ITF composes a test target from declarations instead of coding it as a class. The words are defined in
:doc:`model`. Three layers, each depending only on the one below:

.. code-block:: text

   pytest adapter      score/itf/core/adapters/pytest   discovery, gating, bring-up, fixtures
   ITF core            score/itf/core                   session, realization, probes, execution,
                                                         unwind, the target file format
   OCTO                score/itf/core/octo               the planner: pure standard library

Packs (``score/itf/packs``) and a project's own parts (its ``policy.py``) depend on the core's public
API only, and never on each other. Gates in ``//test/core:gates_test`` keep OCTO free of imports and both
OCTO and the core free of domain words (``ssh``, ``docker``, ``dlt``, ...): domain code lives in packs.

Contracts instead of a class per target
---------------------------------------

A *capability contract* (``exec.command``) is fulfilled by a *capability factory* (``@capability``, label
``docker.exec``); a target file places it under a *role* (``command``), and a test uses it as
``target.command``. A *state contract* (``platform.up``) is fulfilled by an *action* (``@state``, label
``docker.start``) with a probe that checks it. Factories and actions are *parts*. Docker and QEMU are two packs
that fulfil ``platform.instance``: a test written against ``command`` runs on either. To the planner every name
is an opaque string; ITF knows no contracts (see :doc:`model`).

Packs never share code. A factory publishes the shape of what it returns; a consumer (another factory's slot,
an action, a test's ``@itf.requires(..., shape=...)``) states the members it needs with its own Protocol. OCTO
compares the two at every seam.

Two gates
---------

Before any test is collected, OCTO resolves:

1. **Gate 1, what must exist**: factories bound to roles, slots bound, shapes checked, settings validated,
   construction order. Shapes are always checked.
2. **Gate 2, what must happen**: from the goals, the actions to run and their order, from ``after`` (what must
   hold first) and ``breaks`` (what an action destroys), which the actions state themselves and the
   target file adds to with ``relations:``. An action takes part in a scope only if all its slots can be filled
   there (``actions:`` says which role fills a slot with several candidates). Probes run first, so the plan is
   the delta from what already holds. Actions sharing an implementation collapse into one step that verifies
   each state with its own probe.

A failure is one diagnostic naming the gate, not hundreds of red tests. ``itf validate``, ``itf plan`` and
``--itf-plan`` stop here. Resolving is a pure plan: ``Session.resolve()`` builds nothing and probes nothing.

Lifecycle
---------

.. code-block:: text

   load packs from labels → register → publish → compile target file → gate 1 → probe → gate 2
        → select (gating) → bring-up (execute, verify probes) → itf_verify → tests → itf_teardown → unwind

Roles are realized lazily: a deselected test's capabilities are never built. State changes only through the
planner: ``session.reach(state)``; ``session.discard(role)``, which dismantles a role and its dependents and
reaches nothing, so the next access builds them afresh; and ``session.renew(role)``, which is ``discard``
followed by reaching the goals again.

Bazel integration
-----------------

``itf_target`` compiles a target file in a build action and writes its plan. ``py_itf_test(target = ...)``
builds a ``py_test`` that loads the ITF adapter, the packs the target file names, its policy (from the rule's
``srcs``), and the target file and its override files (``ITF_TARGET`` and ``ITF_OVERRIDE``);
``$(location)`` in ``env`` is expanded. Packs ship their tools (dlt-receive, tcpdump) as Bazel-built data found
through runfiles. Run artifacts go to ``$TEST_UNDECLARED_OUTPUTS_DIR/itf-run``; ``--itf-artifacts`` (``none``, ``standard``,
``full``) says how many.

Tests written for the original ``Target`` API run unchanged on the compatibility layer (``score/itf/compat``),
which serves the original plugins over the packs; see :doc:`../how-to/migrate`.
