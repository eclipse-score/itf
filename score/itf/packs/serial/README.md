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

# Serial pack

A serial console, commands over it, and a pseudo-terminal console for setups without hardware.

**Bazel:** `//score/itf/packs/serial`. Packs load from the labels of a target file (`serial.<name>`); never import one pack from another.

| Label | Kind | Contract | What |
|---|---|---|---|
| `serial.console` | capability factory | `exec.console` | a serial device (`device`, `baudrate`, ...) |
| `serial.pty_console` | capability factory | `exec.console` | a shell on a pseudo-terminal, same object and members |
| `serial.exec` | capability factory | `exec.command` | run a command on the console |
| `serial.open` | action | `console.open` | open the console |

**Host prerequisites**

- the serial device

**Target file excerpt**

```yaml
capabilities:
  console:
    factory: serial.console
    with:
      device: /dev/ttyUSB0
  command: serial.exec
goals:
  - console.open
```
