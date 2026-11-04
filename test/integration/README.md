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

# Integration tests: one suite, many target files

The words are defined in the glossary of [the model](../../docs/concepts/model.md#the-vocabulary).

Tests are written once, against roles, and gated on them with `@itf.requires("<role>", contract=..., shape=[...])`;
the test uses the role as `target.<role>` (`"command"`, `"files"`, `"platform"`). Each `py_itf_test` in `BUILD` runs the
**same** suite against a different target file (`itf_target`, compiled during the build); the planner knows what each
target file's platform provides, so every target file runs exactly the tests its platform supports and lists the others as
deselected, with the reason (`--test_output=all`). Supporting a new platform is adding a target file, not touching a test.

```
suite/       generic tests, one file per area (command, process, files, shell, platform, ping, console, logs)
specific/    tests needing one platform's equipment, still gated by shape: a container, a VM's second disk, DLT on the
             target, and the override file's values
targets/     one directory per target (<name>/<name>.itf.yaml); at the top only what several share: policy.py (the
             project's dlt-daemon, the readiness checks), localhost.itf.yaml and qemu.itf.yaml (included or used
             by several targets); the target file itself comes from configuration (`py_itf_test(target = ...)`)
conftest.py  pytest's part: one log line per scenario and verdict
overrides/   an override file: the facts of one setup, merged by role into a target file
```

| Test | Target file | Platform |
|---|---|---|
| `:localhost` | `localhost.itf.yaml` | the test host (runs anywhere, no daemon) |
| `:localhost_override` | `localhost.itf.yaml` + `overrides/localhost.itf.yaml` | the same host, with the platform's working directory from an override file |
| `:serial` | `serial/serial.itf.yaml` | a serial console on a pty shell; `command` goes through it (runs anywhere, no hardware) |
| `:docker` | `docker/docker.itf.yaml` | a container through the Docker API only |
| `:ssh` | `docker_ssh/docker_ssh.itf.yaml`, or `qnx/qnx.itf.yaml` when building for QNX (a `select()`) | a container running sshd: SSH, SFTP, a shell session |
| `:dlt_receive` | `dlt_receive/dlt_receive.itf.yaml` | a dlt-daemon container; dlt-receive TCP capture |
| `:qnx_port_forwarding`, `:ubuntu`, `:ebclfsa` | `qemu.itf.yaml` | QEMU machines (manual) |

Packs state no ordering between their actions and another pack's, so each target file says its own with `relations:`
(for instance `shell.open` after `platform.up` in `docker_ssh/docker_ssh.itf.yaml`).

What each target file selects (✓ ran, · deselected by gating, — file not in that test's target file), from a run
against Podman:

| Test | `local` | `docker` | `docker_ssh` | `dlt_receive` |
|---|---|---|---|---|---|
| command: a failing command reports its exit code without raising | ✓ | ✓ | ✓ | ✓ | ✓ |
| command: output and exit code are returned | ✓ | ✓ | ✓ | ✓ | ✓ |
| command: stderr is part of the output | ✓ | ✓ | ✓ | ✓ | ✓ |
| console: the console recorded output since it opened | · | · | · | · | · |
| container: renew starts from a clean container | — | ✓ | ✓ | — | — |
| container: the target file's volume is mounted | — | ✓ | ✓ | — | — |
| dlt on target: a custom output file is used | — | — | — | ✓ | ✓ |
| dlt on target: receivers stop when their block ends | — | — | — | ✓ | ✓ |
| dlt on target: receives over tcp | — | — | — | ✓ | ✓ |
| dlt on target: receives over udp multicast | — | — | — | ✓ | ✓ |
| files: an uploaded file is visible to commands | ✓ | ✓ | ✓ | ✓ | ✓ |
| files: remote file management | · | · | ✓ | · | · |
| files: upload then download round trips | ✓ | ✓ | ✓ | ✓ | ✓ |
| logs: a message sent on the target is received | · | · | · | ✓ | ✓ |
| logs: a window records only its own block and answers queries | · | · | · | · | ✓ |
| ping: the host pings the target | · | · | · | · | · |
| ping: the target pings its gateway | · | · | · | · | · |
| platform: after a restart reach brings every goal back | ✓ | ✓ | ✓ | ✓ | ✓ |
| platform: renew gives a new platform and reaches the goals again | ✓ | ✓ | ✓ | ✓ | ✓ |
| process: a process reports pid running and exit code | ✓ | ✓ | ✓ | ✓ | ✓ |
| process: cwd is honoured | ✓ | ✓ | ✓ | ✓ | ✓ |
| process: output is captured | ✓ | ✓ | ✓ | ✓ | ✓ |
| process: stop terminates a long running process | ✓ | ✓ | ✓ | ✓ | ✓ |
| process: wrapped processes coordinate | ✓ | ✓ | ✓ | ✓ | ✓ |
| shell: a command running too long reports minus one | · | · | ✓ | · | · |
| shell: line splitting is preserved | · | · | ✓ | · | · |
| shell: run returns stdout and raises on failure | · | · | ✓ | · | · |
| shell: stdout and stderr can be kept apart or merged | · | · | ✓ | · | · |
| **selected** | **12** | **14** | **19** | **17** | **18** |

On the QEMU target files the console and ping tests are selected too (`console: qemu.console`, `ping: ping.pinger`), and
the second-disk test on `:ubuntu` and `:ebclfsa`.

The suite also caught a bug while this matrix was built: the ssh `process` reported `-1` for a
stopped process where the container and host `process` factories report `143`. Generic tests hold the factories
of one contract to one behaviour.

## Running

```bash
bazel test //test/integration:localhost                                  # anywhere
bazel test //test/integration:ssh --test_output=all                   # gating decisions in the log
bazel build //test/integration:target_docker_ssh                 # compile a target file, no hardware
bazel test //test/integration:linux_qemu_tests --config=qemu-integration-linux
```

With rootless Podman: `--test_env=DOCKER_HOST=unix:///run/user/$UID/podman/podman.sock`; the DLT
tests load their image with `oci_load`, which needs a `docker` CLI (or a podman shim) and, with
rootless Podman, `--strategy=TestRunner=local`.

## Two versions of the same tests

The suite exists twice, so a project can see what each way of moving to the new ITF costs:

| Directory | Tests | Bazel and invocation | Infrastructure |
|---|---|---|---|
| `legacy/` | ITF's tests from `main`, byte-identical (`legacy:unchanged_test` keeps them so) | `main`'s `BUILD`: `py_itf_test(plugins = ["//score/itf/plugins:docker_plugin"], args = ["--docker-image=..."])` | the compatibility layer (`score/itf/compat`): the original options select a shipped target file, `target` is the original `Target` as a facade over its roles |
| this directory | the same ground rewritten in the new API: `@itf.requires("<role>")`, `target.<role>` | `itf_target` + `py_itf_test(target = ...)` | target files in `targets/`, no compatibility layer |

- **What the compatibility layer entails:** nothing in the tests. `diff -r` of `main`'s `test/integration` against
  `legacy/` shows only `BUILD` additions (the checks), and every change lives in `score/itf/compat` and the
  re-exporting original module paths. A project with its own target API does the same with a `Facade`.
- **What a test refactor entails:** every test in `legacy/` has an equivalent here, in the new API:

| `legacy/` (original API) | Here (new API) |
|---|---|
| `test_docker.py`: runs, exec capability | `suite/test_command.py` |
| `test_docker.py`: skipped for a missing capability | `suite/test_target.py::test_a_test_needing_a_role_the_target_lacks_is_deselected` |
| `test_docker.py`: file transfer, restart | `suite/test_files.py`, `suite/test_platform.py` |
| `test_docker.py`: extra mount | `specific/test_container.py::test_the_target_file_volume_is_mounted` (the target file's volume) |
| `test_exec_output_not_lost.py` | `specific/test_container.py::test_early_output_is_not_lost_when_the_reply_is_read_late` |
| `test_async_exec.py`: pid, running, wait, exit code, stop, cwd, output | `suite/test_process.py` (first five tests) |
| `test_async_exec.py`: args, args with spaces, absolute binary path | `suite/test_process.py::test_arguments_reach_the_binary_one_by_one_spaces_included`, `::test_an_absolute_binary_path_is_used_as_given` |
| `test_async_exec.py`: wrap_exec (coordinate, stop or wait on exit, expected and real exit codes, output) | `suite/test_process.py::test_wrapped_processes_coordinate`, `::test_a_wrapped_process_is_stopped_when_its_block_ends`, `::test_a_wrapped_process_may_end_with_the_exit_code_it_expects` |
| `test_ssh.py`: default user | `suite/test_shell.py::test_the_session_is_logged_in_as_the_target_files_user` |
| `test_ssh.py`: stdout/stderr apart or merged, line splitting, timeout, large output | `suite/test_shell.py` |
| `test_qemu.py`: default user, upload/download, restart | `suite/test_command.py`, `suite/test_files.py`, `suite/test_platform.py` |
| `test_qemu.py`: another user (`target.ssh(username="qnxuser")`) | `specific/test_second_login.py` (a second shell role, `targets/qnx.itf.yaml`) |
| `test_qemu_disk.py` | `specific/test_disk.py` |
| `test_ping.py` | `suite/test_ping.py` |
| `test_dlt.py`: direct TCP, multicast UDP | `suite/test_logs.py::test_a_message_sent_on_the_target_is_received` (the transport is the target file's) |
| `test_dlt.py`: standard and custom configuration | `suite/test_logs.py::test_a_log_stream_the_target_reached_is_active`, `::test_a_window_can_listen_on_other_multicast_groups` |
| `test_dlt.py`: windows with and without stdout, with a filter, with a record | `suite/test_logs.py::test_a_window_logs_what_it_receives_only_when_asked_to`, `::test_a_window_filters_by_application_and_context`, `::test_a_window_records_only_its_own_block_and_answers_queries` |
| `test_dlt_on_target.py` | `specific/test_dlt_on_target.py` (the `dlt_on_target` role) |
| `test_rules_are_working_correctly.py` | `suite/test_target.py` (a project fixture beside the target; only the roles the target file lists) |
| `test_qemu_config_schema.py` | `test/packs/qemu/test_config_schema.py`, `test_resource_configs.py` (no target needed) |
