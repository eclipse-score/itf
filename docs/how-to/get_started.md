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

# Get started

New to ITF? Read [Start here](start_here.md) and follow the [tutorial](tutorial.md) first. This page shows the
smallest real test, file by file.

## Add ITF

```starlark
# MODULE.bazel
bazel_dep(name = "score_itf", version = "...")
```

```
# .bazelrc
common --registry=https://raw.githubusercontent.com/eclipse-score/bazel_registry/main/
common --registry=https://bcr.bazel.build
```

## A first test

```yaml
# target.itf.yaml: what the target is made of
capabilities:
  platform:
    factory: docker.platform
    with:
      image: ubuntu:24.04
  command: docker.exec
goals:
  - platform.up
```

```python
# test_hello.py
import score.itf as itf

@itf.requires("command")
def test_hello(target):
    assert target.command.exec("echo -n 'Hello from target!'") == (0, "Hello from target!")
```

```starlark
# BUILD
load("@score_itf//:defs.bzl", "itf_target", "py_itf_test")

itf_target(
    name = "target",
    src = "target.itf.yaml",
    packs = ["@score_itf//score/itf/packs/docker"],
)

py_itf_test(
    name = "test_hello",
    srcs = ["test_hello.py"],
    target = ":target",
)
```

`platform` and `command` are roles. `docker.platform` and `docker.exec` are labels of capability factories:
`<pack>.<name>`, and the pack is where they come from. `platform.up` is the goal: the state the target must
reach. The test asks for a role, and gets `target.command`. The words are defined in the glossary of
[the model](../concepts/model.md#the-vocabulary).

```bash
bazel build :target                  # compile the target file: target.plan.json; nothing runs
bazel test :test_hello --test_arg=--itf-plan --test_output=all    # the plan and the gating
bazel test :test_hello
```

Without Bazel, name the target file in `pytest.ini` (`itf_target = target.itf.yaml`), in `pyproject.toml`
(`[tool.itf]` with `target = "target.itf.yaml"`), with `ITF_TARGET`, or per run with
`pytest --itf-target target.itf.yaml`. Python modules explicitly listed in the target file's `policies:` hold
the project's ITF code (`itf_verify`, `itf_teardown`, the project's own parts); pytest fixtures stay in
`conftest.py`. This test needs neither. Native ITF does not discover policies by searching directories.

## Add readiness and evidence: the policy

```python
# policy.py
from score.itf.core import hookimpl

@hookimpl
def itf_verify(session):
    """Checked once after bring-up: a target that cannot answer fails here, with a named check."""
    code, output = session.target.command.exec("echo -n ready")
    session.check("command.answers", code == 0 and output.strip() == "ready", detail=f"exit {code}")

@hookimpl
def itf_teardown(session):
    """Collect evidence while the target still runs, before it is unwound."""
```

Select the module in YAML as well as bundling it in the `itf_target`'s `srcs`:

```yaml
# Add to target.itf.yaml
policies:
    - ./policy.py
```

`./policy.py` works when invoked from the directory containing that Python file. Policy paths are absolute
or relative to the invocation working directory, not the YAML file's parent. For example,
`policies: [/home/alice/bench/policy.py]` selects an absolute path. Under `bazel run`,
`BUILD_WORKING_DIRECTORY` supplies the caller's working directory.

For a shared baseline plus Ubuntu-specific contributions, invoke from the project root and declare both:

```yaml
# targets/ubuntu.itf.yaml
policies:
    - policies/common.py
    - policies/ubuntu.py
capabilities:
    platform:
        factory: docker.platform
        with:
            image: ubuntu:24.04
    command: docker.exec
goals:
    - platform.up
```

```starlark
# BUILD at the project root
itf_target(
        name = "ubuntu",
        src = "targets/ubuntu.itf.yaml",
        packs = ["@score_itf//score/itf/packs/docker"],
        srcs = ["policies/common.py", "policies/ubuntu.py"],
)
```

YAML is the source of truth; `srcs` bundles the selected Python files for planning and tests, it does not
select policies. Any Python filename is valid; there is no `policy.py` basename, proximity, or single-file
restriction, and no planner `--policy` selection. Direct `Session`, CLI and pytest load the same YAML
selection, without an implicit `found.policy` contribution. Policy contributions alone do not trigger
actions without goals requiring their states.

Includes merge first, then the target file, then overrides in order. Nonempty `policies:` lists add paths
deterministically and deduplicate them; omitting the key adds no own policies and retains included or
inherited policies. Explicit `policies: []` clears the inherited list. Deduplicating a module does not permit
duplicate part labels across distinct modules: those remain errors. Legacy discovery stays in compatibility
handling, not the native target-file workflow.

## Test properties in the JUnit report

Add score_tooling's `attribute_plugin` to the `plugins` list and decorate tests with `@add_test_properties(...)`:

```starlark
py_itf_test(
    name = "test_hello",
    srcs = ["test_hello.py"],
    plugins = ["@score_itf//:attribute_plugin"],
    target = ":target",
)
```

## Next

- **Choose a starter**: [Start here](start_here.md).
- **Write tests**: [Write tests](write_tests.md): target files, overrides, scopes, gating, `reach`, `discard` and `renew`.
- **Learn the words**: the glossary in [the model](../concepts/model.md).
- **Find factories**: each pack's README has its label table; [the pack reference](../reference/plugins.rst).
- **Write a pack**: [Write a pack](plugins.md).
