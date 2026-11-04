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

Tests are written once, against roles, and gated on them with `@itf.requires("<role>", shape=YourProtocol)`;
the test uses the role as `target.<role>` (`"command"`, `"files"`, `"platform"`). Each `py_itf_test` in `BUILD` runs the
**same** suite against a different target file (`itf_target`, compiled during the build); the planner knows what each
target file's platform provides, so every target file runs exactly the tests its platform supports and lists the others as
deselected, with the reason (`--test_output=all`). Supporting a new platform is adding a target file, not touching a test.

Each module's `itf_requires` declares only the shared minimum roles and API calls. Function decorators add
test-specific requirements, such as file management, process arguments or a console command API. A module
with independent roles has no common role baseline. This preserves applicability for providers with a
narrower valid API instead of requiring the union of every test's needs.

The console tests demonstrate strict requirements: each test owns a small Protocol declaring the methods and
arguments it consumes. For example, `InteractiveConsole.wait_for` declares `since` and `regex` as keyword
parameters. Gating checks the published callable metadata before target construction, not just the presence
of a method named `wait_for`. It allows additional optional parameters but rejects missing keywords, extra
required parameters, and non-callable replacements. Existing member-name lists remain supported as a weaker
check. Protocol annotations document types; this runtime check validates call structure, not return values
or implementation semantics.

## Infrastructure Policy Invariants

The policy may declare `itf_expect = [YourProtocol]`. Unlike `itf.requires`, this does not add a
requirement to any test: it establishes a minimum API for every matching capability in every
scope of sessions using that policy. The shared policy here declares the console recording API
its teardown hook consumes. Targets without a console remain valid; targets with a console must
provide the declared API even when no selected test uses it.

```python
from typing import Protocol

class RecordedConsole(Protocol):
  __contract__ = "exec.console"

  def lines(self, since: int = 0) -> list[str]: ...

itf_expect = [RecordedConsole]
```

Expectations from loaded policies compose: every matching declaration must hold. Validation uses
OCTO's shape diagnostics during resolution, before test collection or target construction. A policy
violation rejects the target in both loose and strict test-gating modes; it is not an optional test
that loose mode may deselect. Policies may be reused through the existing `pytest_plugins` mechanism,
including modules containing only expectations.

An unversioned contract applies to every major of that contract. A declaration such as
`__contract__ = "exec.console@1"` applies only to providers explicitly offering major 1; other declared
majors are separate APIs. A matching provider with an undeclared major is rejected because the policy
cannot establish whether it applies. Expectations neither create missing roles nor select providers.

## Compatibility Preflight

Collection compares every test requirement with the resolved target plan before any bring-up. The report
groups requirements by scope, role, contract and required major, then keeps each exact consumer profile
separate. One provider may support the basic console tests but not the interactive console tests; the group
is then reported as partially compatible, not flattened into a single member list. A test needing several
roles still requires all of them, and all its requirements appear in the report even when an earlier one fails.

| Result | Default / Loose | `--itf-strict-gating` |
|---|---|---|
| All requirements compatible | Run | Run |
| Role or scope absent | Deselect as not applicable | Deselect as not applicable |
| Explicit contract or declared major differs | Deselect as not applicable | Deselect as not applicable |
| Applicable API lacks members or supported calls | Deselect affected tests | Reject collection before bring-up |
| Required major or callable metadata unavailable | Deselect affected tests as unknown | Reject collection before bring-up |

Explicit versions distinguish intentional API families; they do not excuse a mismatch inside the same
family. A provider with no declared major cannot satisfy a test that requires one. A loose run never drops
one requirement and runs the rest of that test. Strict rejection applies to the whole collected run, before
construction, probes, verification hooks or test bodies. This replaces the earlier strict behavior of failing
individual tests during setup, including tests for absent roles.

The grouped summary is logged at INFO. `--itf-plan` prints it without executing; `--itf-artifacts=full`
writes `preflight.json` with each profile's tests, selected provider, expected and offered shapes, and OCTO
diagnostic codes. Existing per-test `gating.json` remains available. This is a structural compatibility
check, not a guarantee of implementation semantics or return-value correctness.

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

## Shared Observability Showcase

Observability is split so command and multicast-DLT checks do not require host packet-capture privileges.
The `*_pcap` targets alone include `suite/test_capture.py` and the `pcap` pack.
`overrides/qemu_serial.itf.yaml` changes the UART transport and swaps `command` from `ssh.exec`
to `serial.exec`.

| Bazel test | Target selection | Tests |
|---|---|---|
| `:observability` | `select()`; Docker by default, QNX/QEMU with SSH under `--config=qemu-integration` | command and console checks; no host tcpdump |
| `:observability_pcap` | `select()`; Docker by default, QNX/QEMU with SSH under `--config=qemu-integration` | only packet-capture window tests; manual/local because they capture on the host |
| `:observability_serial` | fixed QNX/QEMU target with the serial override | command and console checks through serial; no pcap |
| `:observability_serial_pcap` | fixed QNX/QEMU target with the serial override | packet-capture window tests with commands through serial |
| `:qemu_observability_specialist` | fixed QNX/QEMU pcap target | renew the platform and observe fresh UDP packets before and after |

Specialization is implicit in this wiring. There is no specialist pytest marker or category tag.
Common tests declare their own strict Protocols and never import packs or legacy adapters.

The scenario demonstrates these ownership boundaries:

- The pcap target file lists capture and UDP traffic roles; relationships start host capture before the guest
  and open the console before SSH.
- Policy-owned actions have probes. UART connection retries belong to the project's connection action;
-  tests do not reconstruct the target bring-up sequence.
- The policy's `itf_expect` declarations establish capture/console APIs used by infrastructure. `itf_verify`
  checks command readiness and active capture; `itf_teardown` preserves the console transcript and
  session pcap under the run's `observability/` directory.
- The QNX image contains a small POSIX UDP sender fixture built by Bazel. The project's `traffic` role
  emits UDP payloads through the selected command role for packet-capture tests.
- Pcap tests inspect payload content and window isolation. Command tests use `exec.command`
  for fresh output, exit status and output without a trailing newline across every transport. Console
  tests additionally check recording, fresh stream output and `console.run()` output/exit handling directly;
  command execution over SSH does not replace that console coverage. Docker exec is not presented as a raw
  serial console.

Run non-pcap observability, host-pcap capture, and the licensed QNX/serial variants:

```bash
bazel test //test/integration:observability
bazel test //test/integration:observability_pcap --test_output=all
bazel test //test/integration:observability --config=qemu-integration --sandbox_add_mount_pair=/home/iheb/.qnx:/opt/score_qnx
bazel test //test/integration:observability_pcap --config=qemu-integration --sandbox_add_mount_pair=/home/iheb/.qnx:/opt/score_qnx
bazel test //test/integration:observability_serial --config=qemu-integration --sandbox_add_mount_pair=/home/iheb/.qnx:/opt/score_qnx
bazel test //test/integration:observability_serial_pcap --config=qemu-integration --sandbox_add_mount_pair=/home/iheb/.qnx:/opt/score_qnx
bazel test //test/integration:qemu_observability_specialist --config=qemu-integration --sandbox_add_mount_pair=/home/iheb/.qnx:/opt/score_qnx
```

Host packet capture needs `CAP_NET_RAW` (or root) on tcpdump. Bazel builds a separate exec-configuration
binary for the test. After building the pcap target, grant the capability to that exact runfiles binary,
not the fastbuild binary or its `bazel-bin` symlink:

```bash
bazel build //test/integration:observability_pcap
tcpdump="$(readlink -f bazel-bin/test/integration/observability_pcap.runfiles/_main/score/itf/packs/pcap/tcpdump)"
sudo setcap cap_net_raw+ep "$tcpdump"
getcap "$tcpdump"
bazel test //test/integration:observability_pcap --test_output=all --nocache_test_results
```

Reapply `setcap` after rebuilding tcpdump or running `bazel clean`. The pcap target is manual/local: it
requires a host that permits raw capture and must not run inside Bazel's capability-dropping sandbox.

No suite-specific selection flag or new Bazel platform is needed. The current selector covers Docker and
QNX/QEMU; Linux/QEMU observability would need its own recipe and a distinguishing option in the existing
Linux QEMU configuration, rather than treating every Linux platform as a QEMU guest.

The mount is this development machine's license configuration, not a repository requirement; adjust it
for the host. Docker observability uses Linux host networking and a read-only mount of the Linux-built
UDP sender. Access to a Docker daemon alone does not grant packet-capture privileges to the test process.
Multicast must be routed on the host's default interface. All four console cases are inapplicable to Docker;
the common command/multicast suite runs without tcpdump, and packet capture is selected separately.

The target's `files` supplies target-built images, traffic binaries and configuration; `tools` supplies
execution-platform tcpdump to the pcap target. This distinction matters when QNX is
the target but the test and tcpdump execute on Linux. Both mappings inherit into tests; do not duplicate
their inputs in the test rule.

### Pre-Merge Gates

Ordinary CI excludes the manual, licensed QNX targets. Before merging changes to QEMU, serial capture,
multicast, or their image/policy, run both common selections and the fixed renewal target on a licensed
host with user/network namespaces and QEMU installed. Preserve the three test logs and undeclared outputs,
including `itf-run/preflight.json`, the console transcript, pcap windows and multicast DLT recording.
A build-analysis success is not a runtime pass. QNX TCG coverage is required; KVM and Linux-image QEMU
coverage are separate environment gates, not inferred from a TCG run.

Container changes additionally run native Docker and Docker/SSH targets, their conformance targets,
and the unchanged legacy Docker/SSH suites. Record any unavailable image or daemon prerequisite explicitly.
The throwaway local runner under `tasks/` may collect these logs, but it is not a repository CI dependency.

Verification on 2026-11-10 used QNX SDP 8.0.3 and QEMU 6.2 TCG. The native pytest adapter first passed
11 common tests with QEMU console/SSH, the identical 11 with the serial override, and the isolated renewal
scenario. The complete Bazel runner subsequently passed all six configurations with fresh artifacts:
both common selections, renewal, host PTY, SSH API and pcap cleanup. This exposed and fixed an asset
visibility error and a host/target configuration error: tcpdump must be supplied through execution-built
``tools``, not cross-compiled through QNX ``files``. Docker and Docker/SSH native, conformance and unchanged
legacy Bazel targets also completed successfully. KVM was not exercised; these results do not imply KVM
or Linux-image QEMU coverage.

The planning [benchmark report](../../tools/benchmark/native-qemu-2026-11-10.md) records real and
synthetic cases. Its QEMU warm median was 8.82 ms, cold plan 0.34 s; all 15 cases passed the existing
thresholds. Planning performance is separate from guest boot and test execution time.

## Existing Integration Targets

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
