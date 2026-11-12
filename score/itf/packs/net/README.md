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

# Net pack

Static descriptors: where a service listens and how to log in.

**Bazel:** `//score/itf/packs/net`. Packs load from the labels of a target file (`net.<name>`); never import one pack from another.

| Label | Kind | Contract | What |
|---|---|---|---|
| `net.endpoint` | capability factory | `descriptor.endpoint` | `host` and `port` |
| `net.key` | capability factory | `descriptor.credentials` | a user and a private key file |
| `net.password` | capability factory | `descriptor.credentials` | a user and a password |

**Host prerequisites**

- none

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
```
