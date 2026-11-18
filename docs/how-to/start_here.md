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

# Start here

ITF composes a test target from self-describing parts: a target file says what the target is made of, ITF
plans it from the parts' own metadata, and your tests ask for what they need. Three questions lead you to a
starter. The words are defined in the glossary of [the model](../concepts/model.md#the-vocabulary).

## 1. Where does your software run?

| It runs in | Platform factory | Starter |
|---|---|---|
| a Docker container | `docker.platform` | `examples/examples/starter/container` |
| a machine you reach over SSH (a container with sshd, a QEMU machine, a board) | `docker.platform`, `qemu.platform`, or none for a machine nobody here starts (then `assume:` it is up) | `examples/examples/starter/ssh` |
| a device with a serial console | `serial.console` (hardware) or `serial.pty_console` (no hardware) | `examples/examples/starter/serial` |
| the test host itself | `localhost.platform` | `examples/examples/plain_python` |

## 2. How does ITF reach it?

You choose a capability factory per role. The common ones:

| Role | What a test does with it | Factories |
|---|---|---|
| `command` | run a command, get the exit code and output | `docker.exec`, `ssh.exec`, `serial.exec`, `localhost.exec` |
| `process` | start a program and wrap it | `docker.process`, `ssh.process`, `localhost.process` |
| `files` | copy files in and out | `docker.files`, `ssh.files`, `localhost.files` |
| `shell` | an interactive session | `ssh.shell` |
| `console` | read and write a console, with recorded lines | `serial.console`, `serial.pty_console`, `qemu.console` |
| `logs` | DLT messages | `dlt.receive`, `dlt.receive_tcp` |

Swapping how commands run is changing one word, `command: docker.exec` to `command: ssh.exec`; the test does not
change. Every pack's README lists its labels; the [list of packs](../reference/plugins.rst) lists all of them.

## 3. What do your tests need?

A test asks for roles: `@itf.requires("command")` and `target.command`. It can narrow the ask with
`contract=` and `shape=`. A test whose role the target lacks is deselected with the reason, so one test file can
run on several target files and each runs what it supports (`examples/examples/exec_everywhere`).

## What to run, in order

From the repository root, copy a starter inside the `examples/` MODULE. In the copied
`examples/my_ecu/targets/target.itf.yaml`, change `policies:` to
`[examples/my_ecu/targets/policy.py]` as well as the `# CHANGE:` settings. Keep the module in the copied
`itf_target.srcs`. The commands run from the MODULE root because policy paths resolve from working directory,
not the YAML parent; copying alone does not rewrite the original starter's policy path.

```
cd examples
cp -r examples/starter/container examples/my_ecu
# Edit the copied YAML policy path and the # CHANGE: settings before continuing.
itf validate examples/my_ecu/targets/target.itf.yaml
itf graph examples/my_ecu/targets/target.itf.yaml
itf up --detach examples/my_ecu/targets/target.itf.yaml
itf down examples/my_ecu/targets/target.itf.yaml
itf test examples/my_ecu/targets/target.itf.yaml -- examples/my_ecu
```

With Bazel, `itf` is `bazel run @score_itf//score/itf/cli:itf --` and
`bazel test //examples/my_ecu:test` runs the same tests. `BUILD_WORKING_DIRECTORY` supplies caller cwd.
The commands that do not touch hardware (`validate`, `plan`, `graph`) are safe anywhere, including CI.

## Next

- [Tutorial](tutorial.md): copy a starter, validate, graph, bring up, test, swap a factory, override for one setup.
- [Get started](get_started.md): the smallest real files, from `MODULE.bazel` to a test.
- [The model](../concepts/model.md): the glossary and where each fact lives.
- [Use, define and enforce contracts](contracts.md): contracts are your project's own.
