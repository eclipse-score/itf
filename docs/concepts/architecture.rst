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

This page explains the core design decisions in ITF: the target abstraction
layer, the capability system, the plugin lifecycle, and how ITF integrates
bidirectionally with Bazel.

.. plantuml:: itf_architecture.puml

Target abstraction layer
------------------------

The central concept in ITF is the ``Target``. A target represents the device
or environment under test — a Docker container, a QEMU virtual machine, or
real hardware. All target types expose the same interface, so test code does
not need to know which environment it runs on.

.. code-block:: python

   class Target:
       def execute(self, command): ...
       def upload(self, local_path, remote_path): ...
       def download(self, remote_path, local_path): ...
       def restart(self): ...
       def get_capabilities(self) -> Set[str]: ...

A test that calls ``target.execute("uname -a")`` runs unchanged against a
Docker container or a QEMU VM. The target type is determined at build time by
the ``plugins`` attribute on ``py_itf_test``, and at run time by the CLI
args (e.g. ``--docker-image``) that configure the chosen plugin.

Capability system
-----------------

Different target environments support different operations. A plain Docker
container supports ``exec`` and file transfer but not SSH or SFTP unless an
SSH server is installed. A QEMU VM provides SSH, SFTP, and network-level
operations.

Each ``Target`` subclass declares its capabilities, either by passing them
to the base constructor or by relying on ``Target.REQUIRED_CAPABILITIES``
(``exec``, ``file_transfer``, ``restart``), which is always merged in.
``DockerTarget`` uses only the required capabilities, so it passes no
extras:

.. code-block:: python

   class DockerTarget(Target):
       def __init__(self, container):
           super().__init__()  # capabilities come from REQUIRED_CAPABILITIES
           self.container = container

Tests can be guarded against targets that lack required capabilities using the
``@requires_capabilities`` decorator:

.. code-block:: python

   from score.itf.plugins.core import requires_capabilities

   @requires_capabilities("ssh", "sftp")
   def test_file_roundtrip(target):
       ...

If the active target does not provide all listed capabilities, pytest skips the
test with a clear message. This keeps test suites portable: the same file can
run against Docker for fast feedback and against a QEMU VM for full-system
integration, skipping tests that do not apply.

Tests can also query capabilities at runtime and branch accordingly:

.. code-block:: python

   def test_adaptive(target):
       if target.has_capability("ssh"):
           with target.ssh() as ssh:
               ssh.execute_command("echo hello")
       else:
           exit_code, _ = target.execute("echo hello")

Plugin lifecycle
----------------

Each plugin contributes a ``target_init`` pytest fixture. ITF's core plugin
calls this fixture to obtain the target instance, then wraps it in the
``target`` fixture that test functions receive.

The lifecycle for a single test is:

1. **Setup**: The plugin's ``target_init`` fixture starts the target
   (spins up a container, boots a QEMU VM, connects to hardware).
2. **Test execution**: The test function receives the ``target`` fixture
   and exercises the system under test.
3. **Teardown**: ``target_init`` tears down the target (stops the
   container, shuts down the VM).

With ``--keep-target``, steps 1 and 3 run once per session instead of once
per test function. This is faster but means tests share target state, so it
should only be used when tests are designed to be order-independent.

**Plugin loading order is deterministic but should not be relied upon.**
The core plugin is always registered first. The remaining plugins are
registered with pytest in the exact order they are listed in
``py_itf_test.plugins``. While this order is stable, plugins are designed
to be independent of each other — no plugin should depend on another
plugin's initialisation having completed first.

Why a plugin-based design
--------------------------

Plugin-based design was chosen for three reasons:

**Separation of concerns.** Target management logic (starting containers,
booting VMs) is entirely isolated from test logic. A test that calls
``target.execute()`` has no dependency on Docker or QEMU APIs.

**Extensibility without forking.** Custom targets (real hardware, emulators,
cloud VMs) are added by implementing ``Target`` and ``target_init`` in a new
plugin. No changes to the ITF core are needed.

**Bazel-native composition.** Because plugins are declared as Bazel targets
with ``py_itf_plugin``, they carry their own Python libraries, data files,
and CLI args. Combining plugins — for example Docker + DLT — is as simple as
listing both labels in ``py_itf_test.plugins``. Bazel resolves transitive
dependencies automatically.

Bidirectional Bazel integration
---------------------------------

ITF integrates with Bazel in both directions:

**Build-time** (Bazel → ITF): The ``py_itf_test`` symbolic macro creates a
``py_test`` binary that bundles the test code and all plugin Python
libraries. Plugin CLI args (e.g. ``--docker-image``, paths from
``$(location ...)``) are resolved at analysis time and baked into a launcher
script. This means test hermetically carry their full dependency graph,
including container images or QEMU images referenced via Bazel labels.

**Run-time** (ITF → Bazel): ITF uses Bazel's runfiles mechanism to locate
data files at runtime. The ``$(location ...)`` substitution in ``args``
produces runfiles-relative paths that work regardless of where Bazel places
files in the output tree. Test results are reported via JUnit XML to
``$XML_OUTPUT_FILE``, integrating with Bazel's native test reporting and
caching.

This design means ITF tests participate fully in Bazel's incremental build
and caching: a test is only re-run if its source, its dependencies, or its
configuration changes.
