<!--
*******************************************************************************
Copyright (c) 2025 Contributors to the Eclipse Foundation
See the NOTICE file(s) distributed with this work for additional
information regarding copyright ownership.
This program and the accompanying materials are made available under the
terms of the Apache License Version 2.0 which is available at
https://www.apache.org/licenses/LICENSE-2.0
SPDX-License-Identifier: Apache-2.0
*******************************************************************************
-->

# score.itf.plugins: the original plugin paths

ITF's original plugin modules and Bazel labels (`//score/itf/plugins:docker_plugin`, `qemu_plugin`, `dlt_plugin`,
`core_dump_plugin`, `core_plugin`, `attribute_plugin`), kept so existing BUILD files and imports stay valid. Every
module here only re-exports, from `score/itf/compat` or a pack; `//test/integration/legacy:shims_test` fails on
anything else. The layer itself and how it works: `score/itf/compat/README.md`.
