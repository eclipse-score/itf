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

# Tutorial

Fifteen minutes: copy a starter, validate and draw the target, bring it up, run a test, swap one factory, and
change a value for one setup. The words are defined in the glossary of [the model](../concepts/model.md#the-vocabulary). It needs a Docker-compatible daemon (`DOCKER_HOST` for Podman). `itf` below is
`bazel run @score_itf//score/itf/cli:itf --` under Bazel, or just `itf` with a pip install. Run these commands
from the `examples/` MODULE root: the policy paths are relative to invocation working directory, not the
YAML parent. Under `bazel run`, `BUILD_WORKING_DIRECTORY` supplies the caller's working directory.

## 1. Copy the container starter

```
cd examples
cp -r examples/starter/container examples/my_ecu
```

The copied folder has a test and a `BUILD`, and in `targets/` the target file (`target.itf.yaml`), an
override file (`override.itf.yaml`) and a policy (`policy.py`). Update the copied YAML's `policies:` to
`examples/my_ecu/targets/policy.py`; copying does not rewrite the original starter's path. Keep the file in
`itf_target.srcs`, which bundles it for planning and tests; YAML selects it, with no directory discovery.
The target file after updating that path:

```yaml
# A Docker container from an image, reached through the container API.
# Copy this folder and change what is marked `# CHANGE:`.
policies:
  - examples/my_ecu/targets/policy.py
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

A few lines say what the target is. `platform`, `command` and `files` are **roles**: names tests use. Each is
filled by a **capability factory** (`docker.platform`, `docker.exec`, `docker.files`), and `platform.up` is the
**goal**: a state that must be true once the target is up. The `# CHANGE:` marks are what you edit for your own
software: the image.

The test asks for roles, and uses them as `target.<role>`:

```python
@itf.requires("command")
def test_run_a_command(target):
    code, out = target.command.exec("echo hello-itf")
    assert code == 0
    assert "hello-itf" in out
```

## 2. Validate and draw it, without hardware

```
itf validate examples/my_ecu/targets/target.itf.yaml
itf graph examples/my_ecu/targets/target.itf.yaml
```

`validate` checks every rule from the parts' metadata: each slot has a candidate with the shape it expects, the
settings fit their schemas, the actions can be ordered. `graph` prints the roles, their wiring and the bring-up
sequence as Mermaid: `docker.exec` and `docker.files` need `platform`; the action `docker.start` makes `platform.up`
true first. Under Bazel the build does the same: `bazel build //examples/my_ecu:target` compiles the target file and writes
`target.plan.json`, and fails with ITF's diagnostics when it does not compile.

## 3. Bring it up

```
itf up --detach examples/my_ecu/targets/target.itf.yaml
```

ITF runs the planned actions in order, checks each state with its probe, runs your `itf_verify`, and leaves the
container running. Look at it, then take it down:

```
docker ps
itf down examples/my_ecu/targets/target.itf.yaml
```

`down` needs no state file: it unwinds from what the probes observe.

## 4. Test it

```
itf test examples/my_ecu/targets/target.itf.yaml -- examples/my_ecu
# or: bazel test //examples/my_ecu:test
```

The target is brought up, the tests run against it, and it is torn down. Arguments for pytest go after `--`
(`itf test examples/my_ecu/targets/target.itf.yaml -- examples/my_ecu -k hello`). Evidence (the container's output)
is saved by `itf_teardown` in the policy, while the target still runs.

## 5. Swap a factory

Make the same test run over SSH. Copy `examples/starter/ssh/targets/target.itf.yaml` over yours and reset its
`policies:` path to `examples/my_ecu/targets/policy.py`, or edit your target file:
the platform becomes a container running sshd, `endpoint` and `credentials` tell the `shell` where and how to
log in, `command` becomes `ssh.exec`, and a relation says the session opens only once the container runs:

```yaml
policies:
  - examples/my_ecu/targets/policy.py
capabilities:
  # CHANGE: delete this role for a real machine (and the docker pack in BUILD).
  platform:
    factory: docker.platform
    with:
      image: linuxserver/openssh-server:version-10.2_p1-r0
      command: null
      init: false
      environment: PASSWORD_ACCESS=true,USER_NAME=score,USER_PASSWORD=score
      ports: 2222/tcp  # the port sshd listens on, published by the container
  endpoint:
    # CHANGE: net.endpoint for a real machine, with `host` and `port` under `with`.
    factory: docker.endpoint
    with:
      port: 2222
  credentials:
    # CHANGE: net.key for key authentication (`key_path` replaces `password`).
    factory: net.password
    with:
      user: score
      password: score
  shell:
    factory: ssh.shell
    with:
      n_retries: 20  # how many times to retry the connection while the machine boots
  command: ssh.exec
goals:
  - platform.up
  - shell.open
relations:
  - state: shell.open     # the session connects to a service of the container
    after:
      - platform.up
```

The test file did not change: it still asks for `command` (`test_transfer_a_file` asks for `files`, which this
target file does not list, so it is deselected with the reason). In `BUILD`, add the `net` and `ssh` packs to the
`itf_target`'s `packs` (a label naming a pack that is not listed fails the build, with the label). Run
`itf validate`, `itf graph` and `itf test` again: the graph now shows `ssh.shell` needing `endpoint` and
`credentials`, and `ssh.open` after `docker.start`, because of the relation.

## 6. Override a value for one setup

What differs from one setup to another (a slower machine, another login) goes in an **override file**: a
target file with only what differs:

```yaml
# An override file: merged by role over target.itf.yaml; it holds only what differs in this setup.
capabilities:
  shell:
    with:
      # CHANGE: a slow machine boots slowly: give it more attempts.
      n_retries: 60
  credentials:
    with:
      # CHANGE: this setup's login.
      user: score
      password: score
```

```
itf validate examples/my_ecu/targets/target.itf.yaml --override examples/my_ecu/targets/override.itf.yaml
itf test examples/my_ecu/targets/target.itf.yaml --override examples/my_ecu/targets/override.itf.yaml -- examples/my_ecu
```

The override is merged by role: `with:` keys are merged, other keys replace, `remove: true` takes a role out.
Under Bazel, give it to the target file: `itf_target(name = "target_override", src =
"targets/target.itf.yaml", overrides = ["targets/override.itf.yaml"], ...)` and `py_itf_test(target =
":target_override")`. Without Bazel, set `ITF_OVERRIDE=examples/my_ecu/targets/override.itf.yaml` from the
MODULE root, or pass `pytest --itf-override examples/my_ecu/targets/override.itf.yaml`.

Policy lists are additive across includes and overrides, in deterministic order with paths deduplicated.
Omitting `policies` retains inherited policies; `policies: []` clears them. Duplicate part labels across
distinct modules remain errors. Policy contributions alone do not trigger actions absent goals.

## Where next

- [Get started](get_started.md): the smallest real files.
- [Write tests](write_tests.md): target files, roles, hooks and gating in depth.
- [Use, define and enforce contracts](contracts.md): `itf contracts map` shows every contract name in use.
- [Write a pack](plugins.md): your own factories and actions.
