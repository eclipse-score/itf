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

.. _itf_bazel-macros:

Bazel Macros and Rules
======================

ITF provides three public Bazel build definitions: the ``itf_target`` macro, which compiles a target file
during the build, the ``py_itf_test`` macro for declaring tests, and the ``py_itf_plugin`` rule for declaring the
Bazel target of a pack (or of a plain pytest plugin). The words are defined in the glossary of :doc:`../concepts/model`.

``itf_target``
-------------------

Defined in ``//bazel:itf_target.bzl``. Declare with:

.. code-block:: starlark

   load("@score_itf//:defs.bzl", "itf_target")

   itf_target(
       name = "ecu",
       src = "ecu.itf.yaml",
       overrides = ["lab2.itf.yaml"],
       packs = ["@score_itf//score/itf/packs/docker", "@score_itf//score/itf/packs/ssh"],
       srcs = ["policy.py"],
       files = {"ITF_IMAGE_LOAD": "//images:load"},   # the target file says ${ITF_IMAGE_LOAD}
      tools = {"ITF_TCPDUMP": "//tools:tcpdump"},    # built for the execution platform
   )

The ``itf_target`` supplies every ``${NAME}`` its target file uses: ``files`` for target-built files,
``tools`` for execution-platform files, and ``env`` for other values. Its tests inherit them; a test's own
``env`` can still override a value. It also carries the
Python policy sources named by YAML ``policies:`` to its tests through ``ItfTargetInfo``. For the snippet
above, explicitly declare ``policies: [./policy.py]`` in ``ecu.itf.yaml`` and invoke from the project root
containing that Python file. YAML selects policies; ``srcs`` only bundles the files. There is no required
basename, proximity or single-file restriction, and no planner ``--policy`` selection.

Policy paths are absolute or relative to invocation working directory, not the YAML parent; under
``bazel run``, ``BUILD_WORKING_DIRECTORY`` supplies the caller's working directory. Direct Session, CLI and
pytest use the same selection, without native directory discovery or implicit ``found.policy``. Legacy
handling stays in compat. Includes and overrides add policies in deterministic order and deduplicate paths;
omission retains inherited policies, while explicit ``policies: []`` clears them. Duplicate part labels
across distinct modules remain errors. Contributions do not trigger actions absent goals. See
:doc:`../how-to/get_started` for a common-plus-Ubuntu policy and source-bundling example.

``bazel build :ecu`` loads the packs, compiles the target file exactly as a test run does (both gates, nothing
constructed), writes ``ecu.plan.json`` and fails, printing ITF's diagnostics, when the target file does not
compile or when a factory label names a pack that is not in ``packs``.

.. list-table::
   :header-rows: 1
   :widths: 20 15 10 55

   * - Attribute
     - Type
     - Default
     - Description
   * - ``src``
     - label
     - *mandatory*
     - The target file (YAML).
   * - ``overrides``
     - label list
     - ``[]``
     - Override files: target files holding only what changes, merged by role in this order.
   * - ``packs``
     - label list
     - ``[]``
     - Pack targets (``py_itf_plugin`` with a ``pack`` name) the target file's factory labels may name.
   * - ``data``
     - label list
     - ``[]``
     - Files the target file includes (``include:``), relative to ``src``.
   * - ``srcs``
     - label list
     - ``[]``
     - Python source files named by YAML ``policies:``. Bundles them for planning and tests without
       selecting policies; the tests do not list them again. Any Python filename and multiple modules
       are supported, without requiring them beside ``src``.
   * - ``contracts``
     - label list
     - ``[]``
     - Directories of contract definitions (optional).
   * - ``env``
     - string dict
     - ``{}``
     - Values for the target file's ``${NAME}`` references that are not built files. Used when compiling and
       passed to every test of the target. A ``${NAME}`` that ``env`` does not give (a login) compiles as the
       placeholder ``${NAME}``, since compiling builds nothing; the test run must then supply it, for example
       ``bazel test --test_env=SSH_PASSWORD``. Keep secrets out of ``env``.
   * - ``files``
     - dict of name to label
     - ``{}``
     - Built files the target file refers to: ``{"ITF_IMAGE_LOAD": "//images:load"}``. Every test of the target
       gets the file in its runfiles and ``${NAME}`` set to its path, so tests need no ``data`` or
       ``$(location)``. While compiling, ``${NAME}`` is the label written as a path: nothing is opened, so the
       check never builds or downloads the file.
   * - ``tools``
     - dict of name to label
     - ``{}``
     - Host-executed tools, with the same environment/runfiles behavior as ``files``, but built in the execution
       configuration. Keep guest images in ``files`` and host tools such as tcpdump in ``tools``. A name cannot
       appear in both mappings.

``py_itf_test``
---------------

Defined in ``//bazel:py_itf_test.bzl``. Declare with:

.. code-block:: starlark

   load("@score_itf//:defs.bzl", "py_itf_test")

Minimal example:

.. code-block:: starlark

   py_itf_test(
       name = "test_example",
       srcs = ["test_example.py"],
       target = ":ecu",          # an itf_target: the target file this test runs against
   )

Attributes
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 15 10 55

   * - Attribute
     - Type
     - Default
     - Description
   * - ``srcs``
     - label list
     - *mandatory*
     - Test source files (``.py``). Passed as positional arguments to pytest.
   * - ``plugins``
     - label list
     - ``[]``
     - List of ``py_itf_plugin`` targets for pytest plugins and packs without capabilities (``core_dump``, the
       ``dlt`` ``on_target`` fixture). Each contributes CLI args and runfiles to the test. The packs of a
       target file come from its ``packs``.
   * - ``target``
     - label
     - none
     - An ``itf_target``: the target file this test runs against, with its override files and the packs it
       names (their dependencies come from its ``packs``). The target file arrives through ``ITF_TARGET`` and
       ``ITF_OVERRIDE`` (several files separated by ``os.pathsep``). Its YAML-selected policies keep
       ``itf_verify``, ``itf_teardown`` and the project's own capabilities and actions, bundled by the rule's
       ``srcs``: the test does not list them. Pytest fixtures stay in ``conftest.py``.
   * - ``contracts``
     - label list
     - ``[]``
     - Directories of contract definitions (YAML) loaded besides ITF's own, for the test and its plan
       (``ITF_CONTRACTS_PATH``).
   * - ``args``
     - string list
     - ``[]``
     - Extra CLI arguments passed to pytest. Supports
       ``$(location <label>)`` referencing targets in ``data``.
   * - ``data``
     - label list
     - ``[]``
     - Data files built for target configuration (e.g. QEMU images,
       config files). ``$(location ...)`` in ``args`` resolves against
       these targets.
   * - ``data_as_exec``
     - label list
     - ``[]``
     - Data files built for the exec (host) configuration.
   * - ``deps``
     - label list
     - ``[]``
     - Additional Python dependencies for the test binary.
   * - ``pytest_config``
     - label
     - ``@score_itf//:pytest.ini``
     - Custom pytest configuration file. If omitted, the default
       ``pytest.ini`` from the ``score_itf`` repository is used.
   * - ``env``
     - string dict
     - ``{}``
     - Additional environment variables set for the test process.
       ``PYTHONDONOTWRITEBYTECODE=1`` is always set.
   * - ``tags``
     - string list
     - ``[]``
     - Standard Bazel test tags (e.g. ``["requires-network"]``).
   * - ``timeout``
     - string
     - ``"moderate"``
     - Standard Bazel test timeout (``"short"``, ``"moderate"``,
       ``"long"``, ``"eternal"``).
   * - ``size``
     - string
     - ``"medium"``
     - Standard Bazel test size.

``py_itf_plugin``
-----------------

Defined in ``//bazel:py_itf_plugin.bzl``. Declare with:

.. code-block:: starlark

   load("@score_itf//bazel:py_itf_plugin.bzl", "py_itf_plugin")

Example, the Bazel target of a pack:

.. code-block:: starlark

   py_itf_plugin(
       name = "my_plugin",
       pack = "my",                   # the pack's name: the first part of its labels (my.exec)
       enabled_plugins = ["my_plugin"],
       py_library = "//path/to:my_plugin_lib",
       visibility = ["//visibility:public"],
   )

Attributes
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 22 15 10 53

   * - Attribute
     - Type
     - Default
     - Description
   * - ``py_library``
     - label
     - *mandatory*
     - The ``py_library`` target that provides the plugin's Python code.
       Its ``PyInfo`` and ``DefaultInfo`` providers are forwarded so the
       plugin target can be used as a ``py_test`` dependency.
   * - ``pack``
     - string
     - ``""``
     - The pack this target loads, as named in factory labels (``docker`` for ``docker.platform``). An
       ``itf_target`` reads the pack names of its ``packs`` here. Leave empty for a plain pytest plugin.
   * - ``enabled_plugins``
     - string list
     - ``[]``
     - Pytest plugin module paths to activate (passed as ``-p <path>``
       to pytest). Example: ``["score.itf.packs.docker.plugin"]``.
   * - ``plugin_args``
     - string list
     - ``[]``
     - Additional CLI arguments contributed to every test that uses this
       plugin. Supports ``$(location <label>)`` referencing
       ``plugin_data`` targets.
   * - ``plugin_data``
     - label list
     - ``[]``
     - Data files built for target configuration that are required by the
       plugin at runtime.
   * - ``plugin_data_as_exec``
     - label list
     - ``[]``
     - Data files built for exec (host) configuration required by the
       plugin.
   * - ``env``
     - string dict
     - ``{}``
     - Environment variables contributed by the plugin to every test that
       uses it.
