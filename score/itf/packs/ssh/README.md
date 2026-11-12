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

# SSH pack

An SSH session to a machine, commands, processes and SFTP over it.

**Bazel:** `//score/itf/packs/ssh`. Packs load from the labels of a target file (`ssh.<name>`); never import one pack from another.

| Label | Kind | Contract | What |
|---|---|---|---|
| `ssh.shell` | capability factory | `exec.shell` | the session; needs an endpoint and credentials |
| `ssh.exec` | capability factory | `exec.command` | run a command over the session |
| `ssh.process` | capability factory | `exec.process` | start a program over the session |
| `ssh.files` | capability factory | `files.transfer` | SFTP |
| `ssh.open` | action | `shell.open`, `network.reachable` | connect; each state has its own probe |

**Host prerequisites**

- paramiko (pip, locked)

**Target file excerpt**

```yaml
capabilities:
  endpoint:
    factory: net.endpoint
    with:
      host: 192.168.0.10
      port: 22
  credentials:
    factory: net.password
    with:
      user: score
      password: score
  shell: ssh.shell
  command: ssh.exec
goals:
  - shell.open
```

The action does not wait for a platform. When another pack's action starts the machine, say so in the
target file (a fragment, not a whole target file):

```yaml
relations:
  - state: shell.open
    after:
      - platform.up
```
