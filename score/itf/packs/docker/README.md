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

# Docker pack

A container as the platform, reached through the Docker API (works with any image) and, with the ssh pack, over SSH.

**Bazel:** `//score/itf/packs/docker`. Packs load from the labels of a target file (`docker.<name>`); never import one pack from another.

| Label | Kind | Contract | What |
|---|---|---|---|
| `docker.platform` | capability factory | `platform.instance` | the container: image, command, environment, ports, volumes, its own bridge network, image `bootstrap`, coverage extraction |
| `docker.exec` | capability factory | `exec.command` | run a command in the container |
| `docker.process` | capability factory | `exec.process` | start a program in the container |
| `docker.files` | capability factory | `files.transfer` | copy files in and out |
| `docker.endpoint` | capability factory | `descriptor.endpoint` | a service in the container, by IP or published port (`via`) |
| `docker.start` | action | `platform.up` | the container runs |

**Host prerequisites**

- a Docker-compatible daemon (DOCKER_HOST for Podman)
- under rootless Podman, publish ports and use docker.endpoint with via=published

**Target file excerpt**

```yaml
capabilities:
  platform:
    factory: docker.platform
    with:
      image: ubuntu:24.04
  command: docker.exec
goals:
  - platform.up
```
