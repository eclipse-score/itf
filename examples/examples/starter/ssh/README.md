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

# Starter: a machine over SSH

A machine reached over SSH. The demo is a container running sshd; a real machine drops `platform` and makes `endpoint` a `net.endpoint` (override fragment below). Evidence: `machine.txt` (`uname -a; id`).

## The target file

`targets/target.itf.yaml`:

```yaml
# A machine reached over SSH. For the local demo it is a container running sshd; for a real machine delete
# `platform`, replace `endpoint` with a `net.endpoint` (with `host` and `port`), and set the login.
# Copy this folder and change what is marked `# CHANGE:`.
policies:
  - examples/starter/ssh/targets/policy.py
capabilities:
  # CHANGE: delete this role for a real machine (and the docker pack in BUILD), with the platform.up goal
  # and the relation at the end: nothing starts a platform there.
  platform:
    factory: docker.platform
    with:
      image: linuxserver/openssh-server:version-10.2_p1-r0
      command: null
      init: false
      environment: PASSWORD_ACCESS=true,USER_NAME=${SSH_USER},USER_PASSWORD=${SSH_PASSWORD}
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
      # The login comes from the environment or targets/.env (see .env.example), never from this file.
      user: ${SSH_USER}
      password: ${SSH_PASSWORD}
  shell:
    factory: ssh.shell
    with:
      n_retries: 20  # how many times to retry the connection while the machine boots
  command: ssh.exec
goals:
  - platform.up
  - shell.open
relations:
  # The session connects to a service of the container: the container runs first.
  # CHANGE: delete this relation for a real machine (see the platform role above).
  - state: shell.open
    after:
      - platform.up
```

The login is not in the target file: `${SSH_USER}` and `${SSH_PASSWORD}` come from the environment or from
`targets/.env`, which git ignores. Copy `targets/.env.example` to `targets/.env` and set your machine's login;
the target file can then be shared without it. Under Bazel, the `itf_target`'s `env` gives the demo container's
own account.

`targets/override.itf.yaml`, an override file merged by role:

```yaml
# An override file: merged by role over target.itf.yaml; it holds only what differs in this setup.
capabilities:
  shell:
    with:
      # CHANGE: a slow machine boots slowly: give it more attempts.
      n_retries: 60
```

Target file or override? Put in the target file what makes the target this kind of target (the roles, their
factories, the goals). Put in an override file what changes from one setup to another (an image, a login, a retry
count). Running with the override file is `:test_override`; without it, `:test`.

`net.password` and `net.key` are two factories of one pack: `credentials: net.key` switches to key
authentication (`key_path` replaces `password`). For a real machine, an override takes the demo container out
and points the endpoint at the machine (a fragment of an override file, not a whole target file):

```yaml
capabilities:
  platform:
    remove: true
  endpoint:
    factory: net.endpoint
    with:
      host: 10.0.0.7
      port: 22
assume:
  - state: platform.up
    owner: lab
    reason: the machine is powered and booted by the lab
```

The assumption is there because the target file orders `shell.open` after `platform.up`, and an override file can
add relations but not remove them. A copy of this folder edited for a real machine (the role, the goal and the
relation deleted, as the `# CHANGE:` marks say) needs no assumption.

## Commands

From `examples/`, with Bazel (`itf` is `bazel run @score_itf//score/itf/cli:itf --`; with a pip install it is
just `itf`). Stay at this MODULE root: YAML explicitly selects the policy with a path relative to invocation
working directory, not the YAML parent. Under `bazel run`, `BUILD_WORKING_DIRECTORY` supplies caller cwd.
When copying this starter, update `policies:` to the copied module and bundle it in `itf_target.srcs`.
There is no native directory discovery.

```
itf validate examples/starter/ssh/targets/target.itf.yaml
itf graph examples/starter/ssh/targets/target.itf.yaml
itf up --detach examples/starter/ssh/targets/target.itf.yaml
itf down examples/starter/ssh/targets/target.itf.yaml
itf test examples/starter/ssh/targets/target.itf.yaml -- examples/starter/ssh
itf validate examples/starter/ssh/targets/target.itf.yaml --override examples/starter/ssh/targets/override.itf.yaml
```

```
bazel build //examples/starter/ssh:target         # compile the target file: target.plan.json
bazel test //examples/starter/ssh:test            # bring the target up, run test_hello.py, tear down
bazel test //examples/starter/ssh:test_override   # the same with targets/override.itf.yaml merged over it
```

Without Bazel, say which target file a run uses in `pytest.ini` (`itf_target = targets/target.itf.yaml`,
`itf_override = targets/override.itf.yaml`), in `pyproject.toml` (`[tool.itf]` with `target` and `override`), with
`ITF_TARGET` and `ITF_OVERRIDE`, or per run with `pytest --itf-target ... --itf-override ...`.
The ini example assumes the configuration lives in this starter's folder; keep invocation at the MODULE root
for its policy paths. Explicit CLI/environment paths from there use `examples/starter/ssh/targets/...`.
