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

# Sim pack

In-memory stand-ins for the platform, shell, log stream and capture, for offline runs.

**Bazel:** `//score/itf/packs/sim`. Packs load from the labels of a target file (`sim.<name>`); never import one pack from another.

| Label | Kind | Contract | What |
|---|---|---|---|
| `sim.platform` | capability factory | `platform.instance` | an in-memory platform |
| `sim.exec` | capability factory | `exec.command` | run a command on it |
| `sim.start` | action | `platform.up` | start it |
| `sim.shell` | capability factory | `exec.shell` | an in-memory shell |
| `sim.open` | action | `shell.open`, `network.reachable` | connect it (list `platform.up` in a relation to start the platform first) |
| `sim.logs` | capability factory | `observe.logs` | an in-memory log stream |
| `sim.subscribe` | action | `logs.active` | subscribe to it |
| `sim.capture` | capability factory | `observe.capture` | an in-memory capture |
| `sim.capture_start` | action | `capture.running` | start it |

**Host prerequisites**

- none

**Target file excerpt**

```yaml
capabilities:
  platform:
    factory: sim.platform
    with:
      name: dut
  command: sim.exec
goals:
  - platform.up
```
