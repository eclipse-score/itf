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

`volumes` accepts files or directories as host sources, in Compose-style `host_path:container_path[:mode]` form.
The host path must exist and be accessible to the Docker daemon. Under Bazel, a runfiles directory may contain
symlinks that a Docker daemon cannot follow from a bind mount; use a real host directory visible to that daemon.

## Keeping A Container

Set a unique, stable `name` on `docker.platform` and declare the `platform.up` goal to use `--itf-keep`
or `itf up --detach` and later discover the container.
The container and any ITF-created bridge network carry an ITF ownership label; a fresh session with the
same target file can find them and `itf down` can remove them. A same-name resource without the label is
not adopted. Do not reuse the name for concurrent targets. Without `name`, the generated name is unique to
the session and keeping or detaching the target is refused. Other capabilities in the target must also
support detachment. Docker resources created before this support lack the label and are not adopted.
For a named platform, `docker_sdk_kwargs.labels` must be a JSON object and must not override the ITF label.

## Command Timeout and Cancellation

`docker.exec`'s `timeout` bounds how long ITF waits for the command after starting the Docker exec. It is not
an end-to-end deadline: Docker exec startup and result delivery are outside that wait, and timeout handling
synchronously tries to stop the command before raising `TimeoutError`. Cancellation sends a second Docker exec
to signal the process, then checks whether it stopped at one-second intervals, up to five times, before
escalating to `SIGKILL`. Docker daemon/API latency can add further delay. This polling and escalation behavior
is inherited from the legacy Docker process implementation; a short command timeout therefore does not imply
that the Python call returns within that duration. The timeout stops only the command, not its container.

## Additional Docker SDK Arguments

Common settings remain explicitly typed in ITF. For additional JSON-compatible keyword arguments to
[`containers.run()`](https://docker-py.readthedocs.io/en/7.1.0/containers.html#docker.models.containers.ContainerCollection.run),
use `docker_sdk_kwargs` as a JSON object encoded in a string. This keeps ITF's scalar configuration and
hashable planning format unchanged while allowing nested SDK values:

```yaml
capabilities:
  platform:
    factory: docker.platform
    with:
      image: ubuntu:24.04
      privileged: false
      docker_sdk_kwargs: |-
        {"mem_limit": "256m", "userns_mode": "host", "security_opt": ["no-new-privileges:true"]}
goals:
  - platform.up
```

Use the SDK's exact keyword names and value types, for example `userns_mode`, not `userns`. The SDK
documentation linked above lists available options; support can additionally depend on the daemon and
rootless/Podman environment. Arguments requiring SDK-specific Python objects cannot be expressed as JSON.
Both accepted input forms use the same JSON-compatible value rules: string-keyed objects, lists, strings,
booleans, finite numbers and null. Duplicate JSON object keys and non-finite numbers are rejected. The pack
copies nested input before forwarding it, so SDK processing does not mutate the fixture's options.
Unknown ITF top-level settings still fail schema validation. JSON syntax, object shape, and reserved-key
checks occur when the platform is constructed, before a daemon is contacted; SDK-specific option validation
occurs when starting the container. A typo inside this explicit escape hatch can therefore fail at runtime.

Already-supported ITF settings must stay top-level and cannot be duplicated in `docker_sdk_kwargs`, even
with the same value. ITF also reserves `detach`, `auto_remove`, `remove`, `networking_config`,
`publish_all_ports`, `port_bindings`, `mounts`, and `binds` so passthrough cannot bypass lifecycle,
network/endpoint, and host-mount handling. These restrictions are ownership boundaries, not a sandbox;
additional SDK options can still change container privileges and resource access.

The legacy `docker_configuration` fixture accepts either the same JSON string or a Python dict containing
JSON-compatible values:

```python
@pytest.fixture(scope="session")
def docker_configuration():
    return {"docker_sdk_kwargs": {"mem_limit": "256m", "userns_mode": "host"}}
```

As in the original plugin, a key of that fixture the platform does not name (`mem_limit` here) goes to the SDK
too: `{"mem_limit": "256m"}` is the same as `{"docker_sdk_kwargs": {"mem_limit": "256m"}}`.
