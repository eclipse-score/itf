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

# Illustration: a Raspberry Pi on a hardware bench

An illustrative starting point, not a ready-made bench integration. It shows how a board on a hardware bench maps
onto ITF's model (roles, states, actions, the plan), and how tests written against roles can run on a bench as
well as on a QEMU machine.
Your bench will differ: other instruments, another way to flash, another boot signal, other timings. Treat the
bench pack as a sketch of the parts and the order they run in, and expect to reshape it.

The bench pictured here is a Raspberry Pi:

- a bench power supply switches it on and off;
- an SD-card multiplexer (SDWire, sd-mux) writes its image;
- it answers ping, takes SSH logins with a key and serves files over SFTP;
- it sends DLT to the bench host, and its own DLT daemon can be read on the board.

Ping, SSH, SFTP and DLT come from ITF's packs. The bench is the illustrative pack in `bench_pack/bench`. Its
classes have the members that tests and actions use, and no instrument code: each member raises
`NotImplementedError` naming what it stands for. The glue between them (the board's start and resets, the flash
and start actions) shows one way to compose them; a real bench usually needs more (settling times, retries,
error handling, safety interlocks).

## What runs, in order

`bazel build //examples/rpi_bench:all` compiles the target files without a bench and writes the plan to
`target_rpi.plan.json`:

| Step | Action | Why here |
|---|---|---|
| 1 | `bench.flash` makes `image.flashed` | switches the supply off, writes the card; skipped when the probe says the card already holds the image |
| 2 | `dlt.start_receive` makes `logs.active` | before power-on, so the boot is in the logs |
| 3 | `bench.start` makes `platform.up` | powers the board, waits until it answers ping |
| 4 | `ssh.open` makes `shell.open` | the session that `command`, `process` and `files` use |

At the end of the run the board's teardown switches the supply off.

## The parts

| Role | Factory | From |
|---|---|---|
| `power` | `bench.power_supply` (contract `bench/power.supply`) | the bench pack: `power.py` |
| `flasher` | `bench.sd_flasher` (contract `bench/image.flasher`) | the bench pack: `flasher.py` |
| `platform` | `bench.raspberry_pi` (`platform.instance`): up means powered and answering ping; `restart` reboots over SSH, `power_cycle` switches the supply | the bench pack: `board.py` |
| `endpoint`, `credentials` | `net.endpoint`, `net.key` | ITF's net pack |
| `ping` | `ping.pinger` | ITF's ping pack |
| `shell`, `command`, `process`, `files` | `ssh.shell`, `ssh.exec`, `ssh.process`, `ssh.files` (SFTP) | ITF's ssh pack |
| `logs` | `dlt.receive`: DLT the board sends to the bench host | ITF's dlt pack |
| `dlt_on_target` | `dlt.on_target`: dlt-receive uploaded to the board, reading its own daemon | ITF's dlt pack |

The board is `platform`, as a container or a QEMU machine is elsewhere, and its start delivers the same
`platform.up`. Tests and relations written against `platform.up`, `command` or `files` therefore run here
unchanged. `bench.raspberry_pi` holds no hardware code: it only calls the power supply, the ping role and the
command role. A board with a different boot signal (a serial prompt, a UDS answer) keeps the members and changes
what `start` waits for.

Two resets, for two kinds of test:

- `restart()` (the contract's member) is a soft reset: `sudo reboot` over SSH (`reboot_command` in the settings),
  then the board stops answering ping and answers again. A board that does not go down within `down_timeout` is
  power-cycled instead.
- `power_cycle()` is a hard reset through the supply. It is not part of `platform.instance`, so a test that needs
  it asks for it with a shape, and is deselected on a platform without it (a container, a QEMU machine).

After either, the SSH session is gone; `target.reach()` reopens it.

`bench.flash` declares `breaks=("platform.up",)`: writing the card needs the board off. When a run flashes a
board that is up, the planner starts the board again after flashing.

## Where a real bench takes over

Starting points, not a checklist; each bench brings its own:

1. `bench_pack/bench/power.py`: `on`, `off`, `is_on` and `current` for your supply (SCPI with pyvisa, a USB
   relay, a smart PDU).
2. `bench_pack/bench/flasher.py`: `flash` and `is_flashed` for your multiplexer and writer (`sd-mux-ctrl`,
   `dd`, `bmaptool`). While the board runs, `is_flashed` answers from the last verified flash: a probe never
   switches the card away from a running board.
3. `targets/.env`: copy `targets/.env.example` and set your bench. git ignores `.env`; the environment wins over
   it.
4. Build dlt-receive for the board (aarch64) and point `RPI_DLT_RECEIVE` at it: `dlt_on_target` uploads it.

The test targets are manual (`bazel test //examples/rpi_bench:rpi`). Without a bench, a run stops at the first
stub, e.g. `NotImplementedError: switch on channel 1 of ...`; what a run needs beyond that depends on your bench.

## A card flashed by hand

`targets/preflashed.itf.yaml` assumes `image.flashed` (with an owner and a reason, which the run reports)
instead of writing the card:

```sh
bazel test //examples/rpi_bench:rpi_preflashed
```

The flasher role stays, with stand-in settings. Its pack fills other roles, so the planner still binds the flash
action's slots even though the action never runs.

## The tests

`test_rpi.py` asks for roles, not for a Raspberry Pi: power and current draw, ping, `uname -m` over SSH, a file
round trip over SFTP, DLT from the board to the bench host, DLT recorded on the board, and a reboot and a power
cycle, after each of which `target.reach()` brings every goal back. On a target without one of those roles (a
QEMU machine has no `power`), the test is listed as deselected with the reason.
