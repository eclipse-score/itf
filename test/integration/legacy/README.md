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

# ITF's original tests, unchanged, on the compatibility layer

The test files here are `main`'s integration tests, byte-identical (`unchanged_test` checks every file against
`main_tests.sha256`), and `BUILD` invokes them the way `main` did: `py_itf_test(plugins = [...], args =
["--docker-image=..."])`. They run on the compatibility layer (`score/itf/compat`), so this directory is the proof
that existing tests keep running, and the side-by-side with `test/integration`, where the same ground is written in
the new API. `test/integration/README.md` maps each test here to its rewrite.

Also here: `shims_test` (the original module paths only re-export) and `layer/` (the original target as a facade).
`test_dlt` needs multicast between host and container, which a rootless engine does not route.
