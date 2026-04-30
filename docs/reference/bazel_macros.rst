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

ITF provides two public Bazel build definitions: the ``py_itf_test`` macro
for declaring test targets and the ``py_itf_plugin`` rule for declaring
plugin targets.

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
       args = ["--docker-image=ubuntu:24.04"],
       plugins = ["@score_itf//score/itf/plugins:docker_plugin"],
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
     - List of ``py_itf_plugin`` targets. Each plugin activates a target type
       or supporting capability and contributes CLI args and runfiles to the
       test.
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

Example — defining a custom plugin:

.. code-block:: starlark

   py_itf_plugin(
       name = "my_plugin",
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
   * - ``enabled_plugins``
     - string list
     - ``[]``
     - Pytest plugin module paths to activate (passed as ``-p <path>``
       to pytest). Example: ``["score.itf.plugins.docker"]``.
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
