<!--
*******************************************************************************
Copyright (c) 2026 Contributors to the Eclipse Foundation
See the NOTICE file(s) distributed with this work for additional
information regarding copyright ownership.
This program and the accompanying materials are made available under the
terms of the Apache License Version 2.0 which is available at
https://www.apache.org/licenses/LICENSE-2.0
SPDX-License-Identifier: Apache-2.0
*******************************************************************************
-->

# Adopting ITF without rewriting your tests: a facade

Your project has tests written against its own target class (`target.run(...)`, `target.push(...)`). Moving to
ITF does not mean rewriting them: describe your machines as target files, keep your class as a **facade** over
them, and the tests stay as they are. Only the infrastructure under them changes.

This directory is that move, done for a small project:

| File | What it is |
|---|---|
| `before/ecu.py` | the project's class before ITF: it knew one kind of machine (a container, through the docker command line) |
| `targets/host/host.itf.yaml`, `targets/container/container.itf.yaml` | step 1: what the machines are made of, one target file each |
| `conftest.py` | steps 2 and 3: the same class, `Ecu`, as an `itf.Facade` over the target file's roles, served as `target` |
| `test_ecu.py` | the tests, unchanged; they run on both machines |
| `BUILD` | one `itf_target` and one `py_itf_test` per machine |

## Step 1: describe each machine as a target file

A target file lists the roles a machine offers: `command` (run a command), `files` (move files), and so on, each
from a pack. The host and a container offer the same roles from different packs:

```yaml
capabilities:            # targets/container/container.itf.yaml
  platform:
    factory: docker.platform
    with:
      image: ubuntu:24.04
  command: docker.exec
  files: docker.files
goals:
  - platform.up
```

`bazel build //examples/facade:target_container` checks it without starting anything.

## Step 2: write your class over the roles

Subclass `itf.Facade` and write each method you had over a role. `self.role("command")` is the target file's
`command` role, and fails with what the target file has when it is missing. `CAPABILITIES` answers
`has_capability(...)` from the roles present:

```python
class Ecu(itf.Facade):
    CAPABILITIES = {"exec": ("command",), "flash": ("command", "files")}

    def run(self, cmd):
        code, output = self.role("command").exec(cmd)
        return code, output.decode()
```

Compare it with `before/ecu.py`: the method names and results are the same, and nothing in it knows which
machine it runs on.

## Step 3: serve it as `target`

In `conftest.py`, override `target` with a fixture that wraps ITF's own:

```python
@pytest.fixture(scope="session")
def target(target):
    return Ecu(target)
```

Every name the facade does not define reaches ITF's target, so a new-style test (`target.command.exec(...)`) works
on the same object: the last test in `test_ecu.py` is one.

## Step 4: run, and migrate when you like

```
bazel test //examples/facade:test_host //examples/facade:test_container
```

A new machine is a new target file and a new `itf_target`; the facade and the tests do not change. Move tests to the
new style (`@itf.requires("command")`, `target.command`) one at a time, and delete a facade method when nothing
calls it any more.

## The three ways to run tests on ITF

| You have | Run them | Example |
|---|---|---|
| tests on ITF's original API (`docker_plugin`, `--docker-image`, `target.execute`) | unchanged, BUILD files included: the compatibility layer serves the original API | `test/integration/legacy` (ITF's own original tests) |
| tests on your own target API | a target file plus a facade (this directory); no compatibility layer | `examples/facade` |
| new tests | the new API directly: `itf_target`, `py_itf_test(target = ...)`, `@itf.requires`, `target.<role>` | `test/integration`, `examples/itf`, `examples/starter` |

See docs/how-to/migrate.md for the mapping from the original API to the new one.
