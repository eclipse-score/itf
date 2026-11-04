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

# Ping pack

ICMP echo to an address; also how a machine nobody here starts counts as up.

## Structure

| Location | Responsibility |
|---|---|
| `ping.py` | canonical `Ping`, `ping` and `ping_lost` command-based API |
| `icmp/probe.py` | one echo: datagram socket, raw socket, then binary fallback |
| `icmp/monitor.py` | configured `Pinger`: endpoint validation and wait-up/wait-down polling |
| `providers.py`, `steps.py` | register factories and the boot-readiness action |
| `plugin.py` | pack entrypoint |

`Pinger` derives from `Ping`; it changes the probe backend rather than duplicating the
canonical API. Probing and waiting are separate from target state registration.

**Bazel:** `//score/itf/packs/ping`. Packs load from the labels of a target file (`ping.<name>`); never import one pack from another.

| Label | Kind | Contract | What |
|---|---|---|---|
| `ping.ping` | capability factory | `net.ping` | canonical command-based endpoint ping API |
| `ping.pinger` | capability factory | `net.ping` | ping an endpoint, wait for it to come up or go down |
| `ping.await_boot` | action | `platform.up` | up once the address answers; not beside another platform start |

**Host prerequisites**

- net.ipv4.ping_group_range covering the user, or CAP_NET_RAW, or a ping binary

**Target file excerpt**

```yaml
packs:
  net: score.itf.packs.net.plugin
  ping: score.itf.packs.ping.plugin
capabilities:
  endpoint:
    factory: net.endpoint
    with:
      host: 192.168.0.10
      port: 22
  ping: ping.pinger
goals:
  - platform.up
```
