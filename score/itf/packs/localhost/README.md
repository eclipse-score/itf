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

# Local pack

The test host as the platform: commands, processes and files through subprocess.

**Bazel:** `//score/itf/packs/localhost`. Packs load from the labels of a target file (`local.<name>`); never import one pack from another.

| Label | Kind | Contract | What |
|---|---|---|---|
| `localhost.platform` | capability factory | `platform.instance` | a working directory on the host |
| `localhost.exec` | capability factory | `exec.command` | run a command on the host |
| `localhost.process` | capability factory | `exec.process` | start a program on the host |
| `localhost.files` | capability factory | `files.transfer` | copy files |
| `localhost.start` | action | `platform.up` | the working directory exists |

**Host prerequisites**

- none

**Target file excerpt**

```yaml
capabilities:
  platform: localhost.platform
  command: localhost.exec
goals:
  - platform.up
```
