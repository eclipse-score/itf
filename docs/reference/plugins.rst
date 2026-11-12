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

.. _itf_plugins_reference:

Packs
=====

A pack is loaded from the factory labels of a target file (``docker.exec`` loads ``docker``); under Bazel the
``packs`` of an ``itf_target`` list the pack targets its labels may name. Each pack's own ``README.md`` carries its
label table, host prerequisites and a target file excerpt. The labels below are what a target file puts under
``factory:`` (capability factories) and ``by:`` (actions).

.. list-table::
   :header-rows: 1

   * - Label
     - Capability factories
     - Actions (state)
   * - ``//score/itf/packs/docker``
     - ``docker.platform``, ``docker.exec``, ``docker.process``, ``docker.files``, ``docker.endpoint``
     - ``docker.start`` (platform.up)
   * - ``//score/itf/packs/qemu``
     - ``qemu.platform``, ``qemu.console``, ``qemu.endpoint``, ``qemu.credentials``
     - ``qemu.start`` (platform.up), ``qemu.open_console`` (console.open)
   * - ``//score/itf/packs/ssh``
     - ``ssh.shell``, ``ssh.exec``, ``ssh.process``, ``ssh.files``
     - ``ssh.open`` (shell.open, network.reachable)
   * - ``//score/itf/packs/net``
     - ``net.endpoint``, ``net.key``, ``net.password``
     - none
   * - ``//score/itf/packs/ping``
     - ``ping.pinger``
     - ``ping.await_boot`` (platform.up)
   * - ``//score/itf/packs/dlt``
     - ``dlt.receive``, ``dlt.receive_tcp``, ``dlt.on_target``
     - ``dlt.start_receive`` (logs.active)
   * - ``//score/itf/packs/pcap``
     - ``pcap.capture``
     - ``pcap.start``, ``pcap.start_on_host`` (capture.running)
   * - ``//score/itf/packs/serial``
     - ``serial.console``, ``serial.pty_console``, ``serial.exec``
     - ``serial.open`` (console.open)
   * - ``//score/itf/packs/localhost``
     - ``localhost.platform``, ``localhost.exec``, ``localhost.process``, ``localhost.files``
     - ``localhost.start`` (platform.up)
   * - ``//score/itf/packs/core_dump``
     - the ``itf_teardown`` hook (``--//score/itf/packs/core_dump:extract_core_dumps``)
     - none
   * - ``//score/itf/packs/sim``
     - ``sim.platform``, ``sim.exec``, ``sim.shell``, ``sim.logs``, ``sim.capture``
     - ``sim.start`` (platform.up), ``sim.open`` (shell.open), ``sim.subscribe`` (logs.active), ``sim.capture_start`` (capture.running)

The ``sim`` pack stands in when no daemon or hardware is available. score_tooling's attribute plugin is
``//:attribute_plugin``. A pack states no ordering between its actions and another pack's: a target file says
it with ``relations:``. The original plugins are gone; see :doc:`../how-to/migrate`.
