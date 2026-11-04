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

# Starter: a container

A Docker container from an image: run commands in it, copy files in and out.

## The target file

`targets/target.itf.yaml`:

```yaml
# A Docker container from an image, reached through the container API.
# Copy this folder and change what is marked `# CHANGE:`.
policies:
  - examples/starter/container/targets/policy.py
capabilities:
  platform:
    factory: docker.platform  # CHANGE: another platform factory (qemu.platform, ...) for another machine
    with:
      # CHANGE: the image your software runs in.
      image: ubuntu:24.04
  command: docker.exec
  files: docker.files
goals:
  - platform.up
```

`targets/override.itf.yaml`, an override file merged by role:

```yaml
# An override file: merged by role over target.itf.yaml. It holds only what differs in this setup;
# everything else stays as the target file says.
capabilities:
  platform:
    with:
      # CHANGE: this setup's image (a registry mirror, a build with debug symbols, ...).
      image: debian:12-slim
```

Target file or override? Put in the target file what makes the target this kind of target (the roles, their
factories, the goals). Put in an override file what changes from one setup to another (an image, a login, a retry
count). Running with the override file is `:test_override`; without it, `:test`.

## Commands

From `examples/`, with Bazel (`itf` is `bazel run @score_itf//score/itf/cli:itf --`; with a pip install it is
just `itf`). Stay at this MODULE root: YAML explicitly selects the policy with a path relative to invocation
working directory, not the YAML parent. Under `bazel run`, `BUILD_WORKING_DIRECTORY` supplies caller cwd.
When copying this starter, update `policies:` to the copied module and bundle it in `itf_target.srcs`.
There is no native directory discovery.

```
itf validate examples/starter/container/targets/target.itf.yaml
itf graph examples/starter/container/targets/target.itf.yaml
itf up --detach examples/starter/container/targets/target.itf.yaml
itf down examples/starter/container/targets/target.itf.yaml
itf test examples/starter/container/targets/target.itf.yaml -- examples/starter/container
itf validate examples/starter/container/targets/target.itf.yaml --override examples/starter/container/targets/override.itf.yaml
```

```
bazel build //examples/starter/container:target         # compile the target file: target.plan.json
bazel test //examples/starter/container:test            # bring the target up, run test_hello.py, tear down
bazel test //examples/starter/container:test_override   # the same with targets/override.itf.yaml merged over it
```

Without Bazel, say which target file a run uses in `pytest.ini` (`itf_target = targets/target.itf.yaml`,
`itf_override = targets/override.itf.yaml`), in `pyproject.toml` (`[tool.itf]` with `target` and `override`), with
`ITF_TARGET` and `ITF_OVERRIDE`, or per run with `pytest --itf-target ... --itf-override ...`.
The ini example assumes the configuration lives in this starter's folder; keep invocation at the MODULE root
for its policy paths. Explicit CLI/environment paths from there use `examples/starter/container/targets/...`.
