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

# Pcap pack

A tcpdump capture of an interface.

**Bazel:** `//score/itf/packs/pcap`. Packs load from the labels of a target file (`pcap.<name>`); never import one pack from another.

| Label | Kind | Contract | What |
|---|---|---|---|
| `pcap.capture` | capability factory | `observe.capture` | the capture object |
| `pcap.start` | action | `capture.running` | start it (an interface that exists only once the platform runs: add a relation on `platform.up`) |
| `pcap.start_on_host` | action | `capture.running` | start it on a host interface that already exists, before anything else |

**Host prerequisites**

- CAP_NET_RAW (or root) and the interface on the host

**Target file excerpt**

```yaml
capabilities:
  platform:
    factory: docker.platform
    with:
      image: ubuntu:24.04
  capture:
    factory: pcap.capture
    with:
      interface: docker0
goals:
  - state: capture.running
    by: pcap.start
relations:
  - state: capture.running
    after:
      - platform.up
```
