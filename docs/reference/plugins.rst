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

.. _itf_plugins-reference:

Plugins Reference
=================

Available plugins
-----------------

.. list-table::
   :header-rows: 1
   :widths: 35 20 45

   * - Bazel label
     - Module path
     - Description
   * - N/A
     - ``score.itf.plugins.core``
     - Core plugin. Always active and implicitly enabled. Provides the
       base ``Target`` class, ``@requires_capabilities`` decorator, and
       ``--keep-target`` flag.
   * - ``@score_itf//score/itf/plugins:docker_plugin``
     - ``score.itf.plugins.docker``
     - Docker container target. Starts and stops containers per test (or
       per session with ``--keep-target``). Provides ``exec``,
       ``file_transfer``, and ``restart`` capabilities.
   * - ``@score_itf//score/itf/plugins:qemu_plugin``
     - ``score.itf.plugins.qemu``
     - QEMU virtual machine target. Provides ``ssh``, ``sftp``,
       ``exec``, ``file_transfer``, and ``restart`` capabilities, plus
       ``ping`` / ``ping_lost`` network-testing helpers.
   * - ``@score_itf//score/itf/plugins:dlt_plugin``
     - ``score.itf.plugins.dlt``
     - DLT (Diagnostic Log and Trace) capture plugin. Provides the
       ``dlt_config`` fixture and the ``DltWindow`` context manager for
       capturing and querying DLT messages.
   * - ``@score_itf//score/itf/plugins:attribute_plugin``
     - ``attribute_plugin``
     - Requirement traceability plugin. Provides the
       ``@add_test_properties`` decorator for writing requirement links
       and test classification metadata into the JUnit XML report.

Target capabilities
-------------------

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Capability
     - Provided by
     - Description
   * - ``exec``
     - Docker, QEMU
     - ``target.execute(cmd)`` — run a command and return
       ``(exit_code, output)``.
   * - ``ssh``
     - QEMU
     - ``target.ssh()`` — open an SSH session; returns an ``Ssh``
       object with ``execute_command`` and ``execute_command_output``
       methods.
   * - ``sftp``
     - QEMU
     - ``target.sftp()`` — open an SFTP session; returns an ``Sftp``
       object with ``upload`` and ``download`` methods.
   * - ``file_transfer``
     - Docker, QEMU
     - ``target.upload(local, remote)`` / ``target.download(remote,
       local)`` — copy files to/from the target.
   * - ``restart``
     - Docker, QEMU
     - ``target.restart()`` — restart the target.

Target class API
----------------

All concrete target classes inherit the following public methods from
``score.itf.core.target.Target``.

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Method
     - Description
   * - ``execute(command) -> Tuple[int, bytes]``
     - Run a command synchronously; returns ``(exit_code, output)``.
   * - ``execute_async(binary_path, args=None, cwd="/") -> AsyncProcess``
     - Start a binary without blocking; returns an ``AsyncProcess`` handle.
   * - ``upload(local_path, remote_path) -> None``
     - Copy a file from the test host to the target.
   * - ``download(remote_path, local_path) -> None``
     - Copy a file from the target to the test host.
   * - ``restart() -> None``
     - Restart the target environment.
   * - ``has_capability(capability) -> bool``
     - Return ``True`` if the target supports the given capability string.
   * - ``has_all_capabilities(capabilities) -> bool``
     - Return ``True`` if the target supports every capability in the set.
   * - ``has_any_capability(capabilities) -> bool``
     - Return ``True`` if the target supports at least one capability in
       the set.
   * - ``get_capabilities() -> Set[str]``
     - Return a copy of all capability strings registered on this target.
   * - ``add_capability(capability) -> None``
     - Dynamically register an additional capability on the target instance.
   * - ``remove_capability(capability) -> None``
     - Dynamically remove a capability from the target instance.
   * - ``wrap_exec(...) -> WrappedProcess``
     - Convenience wrapper around ``execute_async`` that returns a
       ``WrappedProcess`` context manager.

CLI arguments
-------------

The following arguments are accepted by their respective plugins at test
runtime. Pass them via ``args`` in ``py_itf_test`` or override at the
command line with ``--test_arg``.

Docker plugin
^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Argument
     - Description
   * - ``--docker-image=<image>``
     - **Required.** Docker image reference (e.g. ``ubuntu:24.04``) used to
       start the container for each test.
   * - ``--docker-image-bootstrap=<cmd>``
     - Command run on the host before the container is started. Use this for
       setup steps that must complete before the test body runs. ``<cmd>``
       should identify the executable/program to invoke; it is not a command
       run inside the container.
   * - ``--extract-coverage``
     - Flag. If set, extracts coverage files (``.gcda``) from the container
       before teardown.
   * - ``--coverage-output-dir=<dir>``
     - Directory to write extracted coverage files. Defaults to
       ``$TEST_UNDECLARED_OUTPUTS_DIR/sysroot`` or ``/tmp/sysroot`` if the
       environment variable is not set.

QEMU plugin
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Argument
     - Description
   * - ``--qemu-config=<path>``
     - **Required.** Path to a JSON configuration file that specifies network
       settings, SSH port, number of CPU cores, and RAM size.
   * - ``--qemu-image=<path>``
     - Path to the QEMU kernel/disk image. Use
       ``$(location <label>)`` in ``args`` to reference a Bazel-built
       image.

DLT plugin
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Argument
     - Description
   * - ``--dlt-receive-path=<path>``
     - Required path to the DLT receive executable used by the plugin.
       When using the Bazel ``dlt_plugin`` label, this argument may be
       provided automatically.
   * - ``--dlt-config=<path>``
     - Optional path to a JSON configuration file with DLT network
       settings (``target_ip``, ``host_ip``, ``multicast_ips``).

Core plugin
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Argument
     - Description
   * - ``--keep-target``
     - Keep the target running across all tests in a session instead of
       creating a fresh target per test function. Speeds up long test
       suites but means tests share target state.
