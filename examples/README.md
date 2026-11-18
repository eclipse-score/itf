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

# ITF examples

ITF composes a test target from self-describing parts (the words are defined in the glossary of
[the model](../docs/concepts/model.md#the-vocabulary)). Each example is a Bazel package with a target file
(`*.itf.yaml`) and a policy that holds only code, both in the example's `targets/` folder, and tests
beside them. A target file lists capabilities by **role**
(`command: docker.exec`), the goals to reach, and settings; tests ask for roles
(`@itf.requires("command", shape=Command)`, `target.command`). `itf_target` compiles a target file during the build and
`py_itf_test(target = ...)` runs tests against it.

Native policies are selected explicitly by YAML `policies:`, not by filename or directory discovery.
These examples declare paths such as `examples/starter/container/targets/policy.py`, relative to this
`examples/` MODULE root. Run the commands below here, not in an example's `targets/` directory. When copying
an example, update its policy paths to the copied modules and bundle those files in `itf_target.srcs`.
YAML selects modules; `srcs` only bundles them. Contributions do not trigger actions absent goals.

Tests declare small consumer Protocols for the calls they use. When every test in a module shares a
requirement, declare it once with `itf_requires = itf.requires("command", shape=Command)`; a list declares
multiple shared requirements. Keep additional roles, methods and keywords on the functions that need them.
Mixed-role examples intentionally retain function-level requirements rather than requiring the union of
their APIs for the entire file. Positional-only Protocol parameters avoid demanding keyword names that
the tests never use. Return annotations document the API; gating does not validate returned object types.

| Example | What it shows |
|---|---|
| `starter/` | three copy-and-edit starters (`container`, `ssh`, `serial`): a target file with `# CHANGE:` marks, an override file, a policy, one test; start here |
| `exec_everywhere/` | one test file on four target files (`container`, `ssh`, `serial`, `serial_device`); the fake ECU's readiness is an action in the project's policy (`policy.py`) |
| `itf/` | `example_app` and `dlt`: one test file on a container, or on a QEMU machine when building for QNX (a `select()` of the target); the project's policy (`policy.py`) starts the DLT daemon |
| `vendor_contract/` | a vendor defines its own contract `acme/power.relay` (no registry), ships a definition and a conformance check in its pack; a factory fulfils it, a test requires the role; `itf contracts map` shows it |
| `facade/` | **tutorial for projects adopting ITF**: a project's own target API (`target.run`, `push`, `pull`) kept as an `itf.Facade` in `conftest.py`; its tests run unchanged on the host and in a container, only the target files are new ([README](examples/facade/README.md)) |
| `plain_python/` | compose and run a target from a script with `Session(target=...)`, without pytest |
| `cpp/`, `docker/` | the example application and the images the examples run |

## Reading a plan

`itf_target` compiles the target file in a build action and writes `<name>.plan.json`; building the
`py_itf_test` builds its target file first, so a bad target file fails the build before any image is built:

```
bazel build //examples/itf:target_docker
cat bazel-bin/examples/itf/target_docker.plan.json
```

The file has three top-level keys: `target` (the roles, the factory chosen for each, and their redacted
settings), `action` (the ordered steps that bring the goals up, each naming the action that runs it) and
`assumptions` (states taken as holding). The output is deterministic, so two plans compare as text.

## The command line

From this `examples/` MODULE root (with Bazel, `itf` is `bazel run
@score_itf//score/itf/cli:itf --`; `BUILD_WORKING_DIRECTORY` supplies the caller's working directory):

```
itf validate examples/starter/container/targets/target.itf.yaml
itf plan examples/starter/container/targets/target.itf.yaml
itf graph examples/starter/container/targets/target.itf.yaml
itf up --detach examples/starter/container/targets/target.itf.yaml
itf down examples/starter/container/targets/target.itf.yaml
itf test examples/starter/container/targets/target.itf.yaml -- examples/starter/container -k hello
itf contracts map examples/starter/container/targets/target.itf.yaml
```

Policy paths are absolute or relative to invocation working directory, never the YAML parent.
`./policy.py` works when invoked where that Python file lives; `/home/alice/bench/policy.py` is an absolute
example. Direct Session, CLI and pytest share the YAML selection; legacy discovery stays in compat.

## Running

From this folder, with a Docker-compatible daemon for the container examples (`DOCKER_HOST` for Podman):

```
bazel build //...
bazel test //...
```
