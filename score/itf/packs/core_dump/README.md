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

# Core dump pack

Explicit collection through composed command and file-transfer slots. The collector
has no pytest dependency, startup action or automatic teardown hook. Its consumer
decides when to collect and where to put the files.

**Bazel:** `//score/itf/packs/core_dump`, listed in the `itf_target` packs.

| Label | Kind | Contract | Shape |
|---|---|---|---|
| `core_dump.collector` | capability factory | `diagnostics.core_dump` | `collect(output_dir) -> list[str]` |

## Target file

```yaml
packs:
	ssh: score.itf.packs.ssh.plugin
	core_dump: score.itf.packs.core_dump.plugin
capabilities:
	# The base target supplies the SSH session.
	command: ssh.exec
	files: ssh.files
	core_dumps:
		factory: core_dump.collector
		bind:
			command: command
			files: files
```

The command slot needs `exec.command` with `exec`; the files slot needs
`files.transfer` with `download`. Missing dependencies fail planning. Use `bind`
when several roles could fill a slot. Add a collector in each device scope that
needs one; there is no implicit first-role selection or cross-scope scan.

## Direct use

```python
import score.itf as itf

@itf.requires("core_dumps", contract="diagnostics.core_dump", shape=["collect"])
def test_with_diagnostics(target, tmp_path):
		try:
				assert target.command.exec("true")[0] == 0
		finally:
				paths = target.core_dumps.collect(str(tmp_path / "coredumps"))
```

The same method works in plain Python sessions and project policy hooks. Call it
while its command and files roles are still available.

## Pytest timing

Project-owned fixtures can collect per test or per session; no extra pack plugin
or command-line mode is required. Choose one of these patterns in `conftest.py`.
These fixtures are optional consumers and do not deselect unrelated tests:

```python
import pytest

@pytest.fixture(autouse=True)
def collect_after_test(target, tmp_path):
		yield
		if target.has("core_dumps"):
				target.core_dumps.collect(str(tmp_path / "coredumps"))
```

Alternatively, for a session-scoped target fixture:

```python
@pytest.fixture(scope="session", autouse=True)
def collect_after_session(target, tmp_path_factory):
		yield
		if target.has("core_dumps"):
				output = tmp_path_factory.mktemp("coredumps")
				target.core_dumps.collect(str(output))
```

Depending on `target` makes collection happen before that fixture is torn down.
A session-scoped collector fixture cannot depend on a function-scoped target.
For mandatory collection, tests declare the requirement shown above rather than
silently skipping collection. These examples use the native role-based target.

## Repeated collection

The first call collects all discovered dumps. Later calls return only new or
content-changed dumps, including a new crash overwriting the same remote filename.
Call once before testing into a baseline directory to separate pre-existing dumps
from test-produced dumps. Tracking belongs to the collector instance; replacing
that role resets the baseline.

Remote files are never deleted. Failed downloads are retried on the next call.
Files mirror their remote paths beneath the chosen output directory. Changed dumps
overwrite the mirrored file if the same output directory is reused; use distinct
per-test directories to preserve earlier versions. Content comparison downloads
each discovered dump to temporary storage on every call.

**Prerequisites:** command and download access to the target's Linux/QNX core-file
locations. No host core-dump tools are required.
