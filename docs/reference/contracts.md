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
# Contracts

This page is generated from the supported contract definitions (`score/itf/packs/*/contracts/*.yaml`) and the
packs' code. Do not edit it by hand: run
`bazel run //score/itf/cli:itf -- contracts reference --output docs/reference/contracts.md`.

ITF knows no contracts: a contract is a name two parts agree on. These are the ones the ITF team maintains for
its own packs, as a supported set and not as a standard. A **capability contract** is fulfilled by a capability
factory (`@capability`) and used in a test through a role; a **state contract** is made true by an action
(`@state`) and listed under `goals:`. A definition adds meaning, a version, members, a suggested role, a
stability and a conformance suite. `itf contracts map` shows every contract in use, with its disagreements.

## Index

| Contract | Kind | Stability | Summary |
|---|---|---|---|
| `application.running` | state | stable | The application under test is running on the target. |
| `capture.running` | state | stable | A packet capture is running. |
| `console.open` | state | stable | A console is open and recording. |
| `descriptor.credentials` | capability | stable | How to log in: a user and a password or a key file. |
| `descriptor.endpoint` | capability | stable | Where a service listens: a host and a TCP port. |
| `diagnostics.core_dump` | capability | stable | Copy the target's core files to the host, when the test or a policy decides to. |
| `exec.command` | capability | stable | Run one shell command and get its exit code and output. |
| `exec.console` | capability | stable | A console (UART, emulator serial port) whose output is recorded from the moment it opens. |
| `exec.process` | capability | stable | Start a program asynchronously and control it through a handle. |
| `exec.shell` | capability | stable | An open shell session with ITF's original `Ssh` command API. |
| `files.transfer` | capability | stable | Copy files between the test host and the target. |
| `image.present` | state | stable | The software image under test is installed on the platform. |
| `logs.active` | state | stable | The session is subscribed to the target's log stream. |
| `logs.on_target` | capability | stable | dlt-receive run on the target itself, started and stopped by the test. |
| `net.ping` | capability | stable | Ask whether a target answers ICMP echo, and wait for it to come up or go down. |
| `network.reachable` | state | stable | The target's endpoint accepts connections from the test host. |
| `observe.capture` | capability | stable | A packet capture the test can start, stop and read. |
| `observe.logs` | capability | stable | Log messages the session receives from the target (DLT), searchable by the test. |
| `platform.instance` | capability | stable | The platform a target runs on, with a lifecycle the planner can bring up and observe. |
| `platform.up` | state | stable | The platform exists and is running. |
| `shell.open` | state | stable | A shell session is connected and can run commands. |

## `application.running`

State contract, version 1, stable. The application under test is running on the target.

- Defined in: `score.itf.contracts.definitions: application.running.yaml`

A project-level state: the pack set does not ship an action for it, a project or product pack delivers it (start the application, wait until it answers). A target file lists it as a goal and relates it to the platform and image states.

### What holding means

Something the project defines, typically a health query on the application.

### See also

- `platform.up`
- `image.present`

### Actions that make it true

None in the supported packs.

### Conformance checks

No checks defined.

## `capture.running`

State contract, version 1, stable. A packet capture is running.

- Defined in: `score.itf.contracts.definitions: capture.running.yaml`

Delivered by the capture action of a pack (on the host or on a platform interface). Anything that sends the traffic under test should require it so the first packets are not lost.

### What holding means

The capture process is alive.

### See also

- `observe.capture`
- `platform.up`

### Actions that make it true

- `pcap.start`
- `pcap.start_on_host`
- `sim.capture_start`

### Conformance checks

No checks defined.

## `console.open`

State contract, version 1, stable. A console is open and recording.

- Defined in: `score.itf.contracts.definitions: console.open.yaml`

Delivered by the action that opens an exec.console node. From then on everything the console prints is recorded. Tests that read boot output rely on this state being reached before the target boots.

### What holding means

The console reports it is open and its reader thread is alive.

### See also

- `exec.console`

### Actions that make it true

- `qemu.open_console`
- `serial.open`

### Conformance checks

No checks defined.

## `descriptor.credentials`

Capability contract, version 1, stable. How to log in: a user and a password or a key file.

- Suggested role: `credentials`
- Defined in: `score.itf.contracts.definitions: descriptor.credentials.yaml`

Data, not behaviour. Secrets are never printed: password and key_path are marked sensitive in config and redacted from plans. An empty password is a valid login on some development images.

### Members

- `user: str` (required): Account name.
- `password: str | None` (required): Password, or None when a key is used.
- `key_path: str | None` (required): Path of a private key file, or None when a password is used.

### Guarantees

- user is a non-empty string.

### See also

- `descriptor.endpoint`
- `exec.shell`

### Capability factories that fulfil it

- `net.key`
- `net.password`
- `qemu.credentials`

### Conformance checks

- `user_is_a_nonempty_string`
- `a_secret_is_a_string_or_none`

## `descriptor.endpoint`

Capability contract, version 1, stable. Where a service listens: a host and a TCP port.

- Suggested role: `endpoint`
- Defined in: `score.itf.contracts.definitions: descriptor.endpoint.yaml`

Data, not behaviour. Clients (SSH, DLT, ping) take an endpoint and connect to it. Factories may take it from configuration (static), from a container's address or published port, or from a virtual machine's port forwarding, so a client never knows which.

### Members

- `host: str` (required): Address or name reachable from the test host.
- `port: int` (required): TCP port, 1 to 65535.

### Guarantees

- host is a non-empty string and port an integer in 1..65535.

### See also

- `descriptor.credentials`
- `net.ping`

### Capability factories that fulfil it

- `docker.endpoint`
- `net.endpoint`
- `qemu.endpoint`

### Conformance checks

- `host_is_a_nonempty_string`
- `port_is_a_valid_tcp_port`

## `diagnostics.core_dump`

Capability contract, version 1, stable. Copy the target's core files to the host, when the test or a policy decides to.

- Suggested role: `core_dumps`
- Defined in: `score.itf.contracts.definitions: diagnostics.core_dump.yaml`

Looks in the usual core file places of Linux and QNX targets with a command and copies each file found through file transfer, mirroring its target path. Collecting is explicit: the consumer chooses when.

### Members

- `collect(output_dir: str) -> list[str]` (required): Copies the core files that are new or changed since the last collect into output_dir and returns their local paths; remote files are kept.

### Guarantees

- A file is never written outside output_dir.
- A core file that has not changed is not copied twice.

### See also

- `exec.command`
- `files.transfer`

### Capability factories that fulfil it

- `core_dump.collector`

### Conformance checks

No checks defined.

## `exec.command`

Capability contract, version 1, stable. Run one shell command and get its exit code and output.

- Suggested role: `command`
- Defined in: `score.itf.contracts.definitions: exec.command.yaml`

The simplest way to act on a target: hand over a command line, get back what happened. Where the command runs depends on the factory (the host, a container, over SSH, on a serial console). Do not rely on state persisting between calls: a factory may start a fresh shell each time, while a console keeps one session. Prefer a child shell (`sh -c '...'`) when a command must not affect the session.

### Members

- `exec(command: str, timeout: float = 30.0) -> tuple[int, bytes]` (required): Returns the exit code and the output as bytes, stdout followed by stderr. A nonzero exit is returned, never raised. A command that does not finish within the timeout is an error of the factory.

### Guarantees

- A nonzero exit code is returned, not raised.
- The output contains what the command wrote to stdout and to stderr.

### See also

- `exec.shell`
- `exec.process`

### Capability factories that fulfil it

- `docker.exec`
- `localhost.exec`
- `serial.exec`
- `sim.exec`
- `ssh.exec`

### Conformance checks

- `output_and_exit_code_are_returned`
- `a_failing_command_reports_its_exit_code_without_raising`
- `stderr_is_part_of_the_output`

## `exec.console`

Capability contract, version 1, stable. A console (UART, emulator serial port) whose output is recorded from the moment it opens.

- Suggested role: `console`
- Defined in: `score.itf.contracts.definitions: exec.console.yaml`

Everything the console prints is kept in a bounded buffer from the moment it opens, including boot messages, so a test can read what happened before it started. `mark` gives a cursor and `lines` / `wait_for` look only at lines received after it. `run` types a command and returns its exit code and output without the echo. The console is opened by the state `console.open`.

### Members

- `open() -> None` (required): Opens the console and starts recording; normally done by the state, not by tests.
- `is_open() -> bool` (required): True while the console is open and its reader is healthy.
- `close() -> None` (required): Stops recording and releases the device; called at teardown.
- `write(text: str) -> None` (required): Sends one line of text (a newline is appended). Raises RuntimeError when not open.
- `mark() -> int` (required): A cursor for lines() and wait_for(); only lines received after this call count.
- `lines(since: int = 0) -> list[str]` (required): The recorded lines, from the cursor `since` (default: everything still buffered).
- `wait_for(pattern: str, timeout: float = 30.0, *, since: int | None = None, regex: bool = False) -> str | None` (required): The first line containing (or matching) the pattern after `since` (default now), or None on timeout.
- `run(command: str, timeout: float = 30.0) -> tuple[int, str]` (required): Runs a shell command on the console; returns exit code and output without echo or marker.

### Guarantees

- Output printed since the console opened is recorded, not only output after the first read.
- lines(since=mark) returns only lines received after the mark was taken.
- run reports the exit code of the command.

### See also

- `exec.command`
- `console.open`

### Capability factories that fulfil it

- `qemu.console`
- `serial.console`
- `serial.pty_console`

### Conformance checks

- `the_console_is_open`
- `the_console_recorded_output_since_it_opened`
- `run_reports_the_exit_code_and_the_output`
- `written_text_is_seen_after_a_mark`

## `exec.process`

Capability contract, version 1, stable. Start a program asynchronously and control it through a handle.

- Suggested role: `process`
- Defined in: `score.itf.contracts.definitions: exec.process.yaml`

For anything that must keep running while the test does something else: servers, load generators, long jobs. `spawn` returns at once with a process handle that reports its pid, whether it still runs, waits for it, stops it and returns what it printed. The handle is also what `score.itf.core.process.WrappedProcess` wraps, so processes from any factory coordinate the same way.

### Members

- `spawn(binary_path: str, args: list[str] | None = None, cwd: str = '/') -> AsyncProcess` (required): Starts the program (a plain command line is accepted as the first argument) in `cwd` and returns without waiting. The handle offers pid(), is_running(), wait(timeout_s), stop(), get_exit_code() and get_output().

### Guarantees

- spawn returns before the program ends.
- wait returns the program's exit code, and the handle then reports it is no longer running.
- stop ends a running program (exit code 143 or 137) and the handle then reports it is not running.
- get_output returns what the program wrote to stdout and stderr.
- The program starts in the requested working directory.

### See also

- `exec.command`

### Capability factories that fulfil it

- `docker.process`
- `localhost.process`
- `ssh.process`

### Conformance checks

- `a_process_reports_pid_running_and_exit_code`
- `stop_terminates_a_long_running_process`
- `output_is_captured`
- `cwd_is_honoured`

## `exec.shell`

Capability contract, version 1, stable. An open shell session with ITF's original `Ssh` command API.

- Suggested role: `shell`
- Defined in: `score.itf.contracts.definitions: exec.shell.yaml`

A connected session (for example SSH) offering the original `Ssh` methods: output split into lines, stdout and stderr kept apart or merged, a bound on how long a command may run (exit code -1 when the command exceeds max_exec_time). Other capabilities (command, process, files) are built on top of one shell. The session is opened by the state `shell.open`.

### Members

- `execute_command_output(cmd: str, timeout: float = 30, max_exec_time: float = 180, logger_in=None, verbose: bool = True, separate_stderr: bool = True) -> tuple[int, list[str], list[str]]` (required): Returns the exit code, the stdout lines and the stderr lines, each line keeping its newline; stderr is merged into stdout unless separate_stderr. The exit code is -1 when the command exceeds max_exec_time.
- `execute_command(cmd: str, timeout: float = 30, max_exec_time: float = 180, logger_in=None, verbose: bool = True) -> int` (required): Returns the exit code; never raises on a nonzero exit.

### Guarantees

- Line splitting preserves each newline.
- A command exceeding max_exec_time reports exit code -1.

### See also

- `exec.command`
- `shell.open`

### Capability factories that fulfil it

- `sim.shell`
- `ssh.shell`

### Conformance checks

- `execute_command_returns_the_exit_code`
- `stdout_and_stderr_can_be_kept_apart_or_merged`
- `line_splitting_is_preserved`
- `a_command_running_too_long_reports_minus_one`

## `files.transfer`

Capability contract, version 1, stable. Copy files between the test host and the target.

- Suggested role: `files`
- Defined in: `score.itf.contracts.definitions: files.transfer.yaml`

Upload and download single files, creating missing directories on the destination. Factories add management members (exists, remove, listdir, upload_dir, download_dir) where the transport supports them; a test that needs them declares its own Protocol with `@itf.requires(role, shape=FileAPI)`.

### Members

- `upload(local_path: str, remote_path: str) -> None` (required): Copies a host file to the target, creating the destination directory. Raises FileNotFoundError when the local file does not exist.
- `download(remote_path: str, local_path: str) -> None` (required): Copies a target file to the host, creating the destination directory.

### Guarantees

- A file uploaded and downloaded again has the same content.
- Missing destination directories are created.
- The target sees the uploaded file at the remote path (a command can read it).

### See also

- `exec.command`

### Capability factories that fulfil it

- `docker.files`
- `localhost.files`
- `ssh.files`

### Conformance checks

- `upload_then_download_round_trips`
- `downloading_creates_the_local_directory`
- `remote_file_management`

## `image.present`

State contract, version 1, stable. The software image under test is installed on the platform.

- Defined in: `score.itf.contracts.definitions: image.present.yaml`

A project-level state for setups that flash or load an image before the platform boots. The pack set ships no action for it; a project delivers it and relates platform.up to it.

### What holding means

Something the project defines, for example the image checksum on the device.

### See also

- `platform.up`
- `application.running`

### Actions that make it true

None in the supported packs.

### Conformance checks

No checks defined.

## `logs.active`

State contract, version 1, stable. The session is subscribed to the target's log stream.

- Defined in: `score.itf.contracts.definitions: logs.active.yaml`

Delivered by the action that connects the observe.logs node; requires the platform to be up (the daemon lives there). Reaching it again after a restart resubscribes.

### What holding means

The stream's reader is alive.

### See also

- `observe.logs`
- `platform.up`

### Actions that make it true

- `dlt.start_receive`
- `sim.subscribe`

### Conformance checks

No checks defined.

## `logs.on_target`

Capability contract, version 1, stable. dlt-receive run on the target itself, started and stopped by the test.

- Suggested role: `dlt_on_target`
- Defined in: `score.itf.contracts.definitions: logs.on_target.yaml`

Receives DLT where the target's own network sees it (multicast inside the target, a target-local TCP daemon). The provider puts the receiver binary on the target on the first start, through the target's files and process roles; each start runs one receiver that records to a file on the target.

### Members

- `start(transport, host_ip='127.0.0.1', target_ip='127.0.0.1', multicast_ips=None, print_to_stdout=True, output_file=None) -> ContextManager[DltReceiver]` (required): Runs one receiver over transport ("tcp", "udp" or Protocol) and stops it when the block ends; the receiver has the process API plus dlt_file, the target path it records to.
- `close() -> None` (required): Stops every receiver still running; called when the role is torn down.

### Guarantees

- Constructing the role touches nothing on the target.
- No receiver started through the role outlives it.

### See also

- `observe.logs`
- `files.transfer`
- `exec.process`

### Capability factories that fulfil it

- `dlt.on_target`

### Conformance checks

No checks defined.

## `net.ping`

Capability contract, version 1, stable. Ask whether a target answers ICMP echo, and wait for it to come up or go down.

- Suggested role: `ping`
- Defined in: `score.itf.contracts.definitions: net.ping.yaml`

The host pings an endpoint. Used as a boot detector (the target is up when it answers) and to wait for a restart to take effect.

### Members

- `host: str` (required): The address being pinged.
- `ping() -> bool` (required): One echo request; True when a reply arrives in time.
- `wait_up(timeout: float | None = None) -> bool` (required): Polls until the target answers; False on timeout.
- `wait_down(timeout: float | None = None) -> bool` (required): Polls until the target stops answering; False on timeout.

### Guarantees

- ping returns a boolean and never raises for an unreachable target.

### See also

- `descriptor.endpoint`
- `network.reachable`

### Capability factories that fulfil it

- `ping.ping`
- `ping.pinger`

### Conformance checks

- `host_is_a_nonempty_string`
- `ping_returns_a_boolean`

## `network.reachable`

State contract, version 1, stable. The target's endpoint accepts connections from the test host.

- Defined in: `score.itf.contracts.definitions: network.reachable.yaml`

Delivered alongside shell.open by the SSH pack, or by a network pack that waits for the endpoint. Routing and forwarding problems show up here instead of as a confusing timeout in a later test.

### What holding means

A TCP connection to the endpoint succeeds.

### See also

- `descriptor.endpoint`
- `shell.open`

### Actions that make it true

- `sim.open`
- `ssh.open`

### Conformance checks

No checks defined.

## `observe.capture`

Capability contract, version 1, stable. A packet capture the test can start, stop and read.

- Suggested role: `capture`
- Defined in: `score.itf.contracts.definitions: observe.capture.yaml`

A capture of network traffic written to a file. It is started by the state `capture.running` (so it is on before the traffic of interest) and stopped at teardown. Factories may add `path` (the capture file) and `window` (capture one block of a test into its own file); neither is required: gate on them with `shape=`.

### Members

- `start() -> None` (required): Starts capturing; normally done by the state, not by tests.
- `stop() -> None` (required): Stops capturing and finalises the file; idempotent.
- `running() -> bool` (required): True while the capture process is alive.
- `pathPath (a property)` (optional): The capture file.
- `window(name: str, ready_timeout: float = 5.0) -> ContextManager[Path]` (optional): Captures one block of a test into its own file, named after `name`, and yields its path.

### Guarantees

- running() is true while a capture is on.

### See also

- `capture.running`

### Capability factories that fulfil it

- `pcap.capture`
- `sim.capture`

### Conformance checks

No checks defined.

## `observe.logs`

Capability contract, version 1, stable. Log messages the session receives from the target (DLT), searchable by the test.

- Suggested role: `logs`
- Defined in: `score.itf.contracts.definitions: observe.logs.yaml`

The session subscribes to the target's log stream and keeps a bounded buffer of decoded messages. Tests read them after the target did something. Factories may add `filter` (by application and context id), which is not required: gate on it with `shape=`. The subscription is made by the state `logs.active`.

### Members

- `is_active() -> bool` (required): True while the stream delivers messages; the probe of the state `logs.active`.
- `lines() -> list[DltMessage]` (required): Every buffered message in arrival order; raises RuntimeError when the stream is dead.
- `filter(apid: str | None = None, ctid: str | None = None) -> list[DltMessage]` (optional): The buffered messages of one application id and context id, in arrival order.

### Guarantees

- A message sent on the target arrives in lines() within seconds.
- Where filter is offered, ids that no message has give an empty list.

### See also

- `logs.active`
- `descriptor.endpoint`

### Capability factories that fulfil it

- `dlt.receive`
- `dlt.receive_tcp`
- `sim.logs`

### Conformance checks

No checks defined.

## `platform.instance`

Capability contract, version 1, stable. The platform a target runs on, with a lifecycle the planner can bring up and observe.

- Suggested role: `platform`
- Defined in: `score.itf.contracts.definitions: platform.instance.yaml`

Constructing the object creates nothing: the action delivering `platform.up` starts it and the teardown stops it. Other nodes (command, process, files, console, endpoint) take a platform as input and use what it exposes. `restart` simulates a reboot; after it, `target.reach()` brings every goal back.

### Members

- `start() -> None` (required): Brings the platform up; called by the action for platform.up, not by tests.
- `running() -> bool` (required): True while the platform is up; the probe of platform.up.
- `restart() -> None` (required): Restarts the platform. Anything connected to it (SSH sessions) is dropped.
- `stop() -> None` (required): Takes the platform down and releases what it created; idempotent.

### Guarantees

- running() is true once the platform is up.
- After restart() the platform is running again within a bounded time.
- stop() can be called more than once.

### See also

- `platform.up`

### Capability factories that fulfil it

- `docker.platform`
- `localhost.platform`
- `qemu.platform`
- `sim.platform`

### Conformance checks

- `the_platform_is_running_once_up`
- `a_restart_leaves_a_running_platform`

## `platform.up`

State contract, version 1, stable. The platform exists and is running.

- Defined in: `score.itf.contracts.definitions: platform.up.yaml`

The root of most plans: command, process, file, console and shell actions require it. Delivered by the start action of the platform's pack (host directory, container, virtual machine) or by waiting for a machine that boots on its own (ICMP). Invalidated by restart.

### What holding means

The platform reports running().

### See also

- `platform.instance`
- `shell.open`

### Actions that make it true

- `docker.start`
- `localhost.start`
- `ping.await_boot`
- `qemu.start`
- `sim.start`

### Conformance checks

No checks defined.

## `shell.open`

State contract, version 1, stable. A shell session is connected and can run commands.

- Defined in: `score.itf.contracts.definitions: shell.open.yaml`

Delivered by the action that connects an exec.shell node (SSH). It requires the platform to be up and is invalidated by anything that drops the connection, such as a restart. Reaching it again after a restart reconnects.

### What holding means

The session reports it is connected.

### See also

- `exec.shell`
- `platform.up`
- `network.reachable`

### Actions that make it true

- `sim.open`
- `ssh.open`

### Conformance checks

No checks defined.
