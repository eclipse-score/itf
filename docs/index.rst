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

Score ITF
=========

Integration Test Framework for ECU testing in automotive domains: a platform to compose test targets from
self-describing parts. A target file says what a target is made of, OCTO plans it from the parts' own
metadata (nothing is trusted on its name), and your tests ask for roles. Write a test once, run it on a
container, a virtual machine or real hardware.

.. grid:: 1 1 2 4
   :class-container: score-grid

   .. grid-item-card::

      :doc:`Start here <how-to/start_here>`
      ^^^
      Three questions that lead you to a starter and the commands to run.

   .. grid-item-card::

      `Contract map <catalog.html>`_
      ^^^
      Every pack, capability factory, action and contract ITF offers, searchable.

   .. grid-item-card::

      :doc:`Tutorial <how-to/tutorial>`
      ^^^
      Fifteen minutes: copy a starter, validate, graph, bring it up, test, swap a factory, override for one setup.

   .. grid-item-card::

      :ref:`Reference <itf_reference>`
      ^^^
      Contracts, Bazel macros (``itf_target``, ``py_itf_test``) and packs.


.. dropdown:: Sitemap

   .. toctree::
      :maxdepth: 5
      :includehidden:
      :titlesonly:

      how-to/start_here
      how-to/tutorial
      how-to/index
      reference/index
      concepts/index
      decisions/index
      manual/index
      release/index
      safety_mgt/index
      security_mgt/index
      verification_report/index
