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

# Bazel rules

Loaded through `@score_itf//:defs.bzl`.

| File | Rule | Does |
|---|---|---|
| `itf_target.bzl` | `itf_target` | compiles a target file in a build action (both gates, nothing constructed); carries its packs, policy, `env` and `files` to the tests that use it |
| `itf_plan.py` | | the planner the build action runs |
| `py_itf_test.bzl` | `py_itf_test` | a pytest run with the ITF adapter: `target = ":x"` (or a `select()` of targets), or ITF's original API through `plugins` and `args` |
| `py_itf_plugin.bzl` | `py_itf_plugin` | a pack or pytest plugin: its library, the plugins to enable, its arguments and data |
| `py_itf_unittest.bzl` | `py_itf_unittest` | a plain pytest run, for unit tests that need no target |
| `target_info.bzl` | `ItfTargetInfo` | what an `itf_target` hands its tests |

## Explicit policy modules

YAML `policies:` is the source of truth; `itf_target(srcs = [...])` bundles the Python files it names for
the planner and tests. It does not select policies. Any Python filename is valid, with no proximity or
single-file restriction and no planner `--policy` selection. For example, from a project's module root:

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
itf_target(
		name = "ubuntu",
		src = "targets/ubuntu.itf.yaml",
		packs = ["@score_itf//score/itf/packs/docker"],
		srcs = ["policies/common.py", "policies/ubuntu.py"],
)
```

Policy contributions alone do not trigger actions without goals requiring their states. Includes and
overrides add policies deterministically and deduplicate paths; omitting the key retains inherited policies,
while explicit `policies: []` clears the inherited list. Duplicate part labels across distinct modules
remain errors.

Policy paths are absolute or relative to invocation working directory, not the YAML parent. `./policy.py`
works when invoked where that file lives; `/home/alice/bench/policy.py` is an absolute example. Under
`bazel run`, `BUILD_WORKING_DIRECTORY` supplies the caller's working directory. Direct `Session`, CLI and
pytest load the same YAML selection, without native directory discovery or implicit `found.policy`.
Legacy discovery stays in compat. The shipped examples use paths relative to the `examples/` MODULE root:
run their documented commands there, not in an individual target directory.

Two details of `py_itf_test`: a test without a target loads the compatibility core plugin first (the original
rule did); the wrapped `py_test` is built for `--host_platform`, as the original rule's `cfg = "exec"` was, so a
`select()` on its deps or plugins sees the same constraints, but with the target configuration's coverage settings,
so `bazel coverage` measures every test, also when the target is built for another platform. Reference:
`docs/reference/bazel_macros.rst`.
