# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************
"""`itf doctor`: does this host have what the packs of a target file need?

The packs come from the factory labels of the target file (`docker.platform` names the pack `docker`); each pack's
prerequisites are listed from its `pack.yaml`, and the ones that can be tested here are tested.
"""

from __future__ import annotations

import glob
import importlib
import importlib.util
import os
import shutil
import socket
import sys
from dataclasses import dataclass
from pathlib import Path

PACK_PREFIX = "score.itf.packs."

# ---------------------------------------------------------------- probes: each returns (ok, detail)


def _unix_path(url: str) -> str | None:
    return url[len("unix://") :] if url.startswith("unix://") else None


def probe_container_engine() -> tuple[bool, str]:
    """A container engine answers on DOCKER_HOST or on a default socket."""
    host = os.environ.get("DOCKER_HOST", "")
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    candidates = [host] if host else ["unix:///var/run/docker.sock"]
    if not host and runtime:
        candidates.append(f"unix://{runtime}/podman/podman.sock")
    problems = []
    for url in candidates:
        path = _unix_path(url)
        try:
            if path is not None:
                with socket.socket(socket.AF_UNIX) as sock:
                    sock.settimeout(2)
                    sock.connect(path)
            elif url.startswith("tcp://"):
                address, _, port = url[len("tcp://") :].rpartition(":")
                socket.create_connection((address, int(port or 2375)), timeout=2).close()
            else:
                problems.append(f"{url}: unsupported scheme")
                continue
        except (OSError, ValueError) as exc:
            problems.append(f"{url}: {exc}")
            continue
        try:
            import docker  # type: ignore[import-not-found]
        except ImportError:
            return True, f"{url} accepts connections (Docker SDK not importable, no ping)"
        try:
            docker.DockerClient(base_url=url).ping()
        except Exception as exc:  # noqa: BLE001  any SDK failure means the engine is not usable
            problems.append(f"{url}: SDK ping failed: {exc}")
            continue
        return True, f"{url} answers a ping"
    return False, "; ".join(problems)


def probe_kvm() -> tuple[bool, str]:
    ok = os.access("/dev/kvm", os.R_OK | os.W_OK)
    return ok, "/dev/kvm is readable and writable" if ok else "/dev/kvm is missing or not accessible"


def probe_qemu() -> tuple[bool, str]:
    systems = sorted(
        {Path(p).name for d in os.environ.get("PATH", "").split(os.pathsep) for p in glob.glob(f"{d}/qemu-system-*")}
    )
    img = shutil.which("qemu-img")
    if systems and img:
        return True, f"{', '.join(systems)} and qemu-img found"
    missing = ([] if systems else ["qemu-system-*"]) + ([] if img else ["qemu-img"])
    return False, f"not on PATH: {', '.join(missing)}"


def _ping_group_range() -> tuple[int, int] | None:
    try:
        low, high = Path("/proc/sys/net/ipv4/ping_group_range").read_text().split()
        return int(low), int(high)
    except (OSError, ValueError):
        return None


def _has_cap_net_raw() -> bool:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("CapEff:"):
                return bool(int(line.split()[1], 16) & (1 << 13))
    except (OSError, ValueError, IndexError):
        pass
    return False


def probe_icmp() -> tuple[bool, str]:
    """An unprivileged ICMP socket: root, CAP_NET_RAW, or a group inside net.ipv4.ping_group_range."""
    if os.geteuid() == 0 or _has_cap_net_raw():
        return True, "root or CAP_NET_RAW"
    span = _ping_group_range()
    if span is not None and any(span[0] <= gid <= span[1] for gid in {os.getegid(), *os.getgroups()}):
        return True, f"a group of this user is inside net.ipv4.ping_group_range {span[0]} {span[1]}"
    return False, f"net.ipv4.ping_group_range is {span if span else 'unreadable'} and there is no CAP_NET_RAW"


def probe_tcpdump() -> tuple[bool, str]:
    found = shutil.which("tcpdump")
    if found:
        return True, found
    try:
        from score.itf.packs.pcap.capture import bundled

        path = bundled("tcpdump")
        if path != "tcpdump" and os.path.exists(path):
            return True, f"bundled: {path}"
    except ImportError:
        pass
    return False, "tcpdump is not on PATH and not bundled"


def probe_module(name: str):
    def probe() -> tuple[bool, str]:
        ok = importlib.util.find_spec(name) is not None
        return ok, f"python module {name} is importable" if ok else f"python module {name} is not installed"

    return probe


# ---------------------------------------------------------------- the checks


@dataclass(frozen=True)
class Check:
    name: str
    probe: str  # the name of a probe function in this module; looked up at run time so tests can patch it
    hint: str
    packs: tuple[str, ...]  # the packs that need it; a check nobody selected is optional
    covers: tuple[str, ...] = ()  # the `prerequisites` of those packs' pack.yaml it checks, word for word


CHECKS = (
    Check(
        "container engine reachable",
        "probe_container_engine",
        "start the daemon and point DOCKER_HOST at it; for rootless Podman:"
        " `systemctl --user enable --now podman.socket` and"
        " `export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock`",
        ("docker",),
        ("a Docker-compatible daemon (DOCKER_HOST for Podman)",),
    ),
    Check(
        "/dev/kvm accessible",
        "probe_kvm",
        "enable virtualization in the firmware, then `sudo usermod -aG kvm $USER` and log in again",
        ("qemu",),
        ("/dev/kvm for acceleration",),
    ),
    Check(
        "qemu-system-* and qemu-img on PATH",
        "probe_qemu",
        "install QEMU, e.g. `sudo apt-get install qemu-system-x86 qemu-system-arm qemu-utils`",
        ("qemu",),
        ("qemu-system-* and qemu-img",),
    ),
    Check(
        "ICMP allowed (ping)",
        "probe_icmp",
        'run `sudo sysctl -w net.ipv4.ping_group_range="0 2147483647"` or grant CAP_NET_RAW',
        ("ping",),
        ("net.ipv4.ping_group_range covering the user, or CAP_NET_RAW, or a ping binary",),
    ),
    Check(
        "tcpdump available (capture)",
        "probe_tcpdump",
        "install tcpdump (`sudo apt-get install tcpdump`) and allow it to capture"
        " (`sudo setcap cap_net_raw+ep $(which tcpdump)`)",
        ("pcap",),
    ),
    Check(
        "paramiko importable",
        "probe_paramiko",
        "install paramiko: `pip install paramiko`",
        ("ssh",),
        ("paramiko (pip, locked)",),
    ),
    Check("pyserial importable", "probe_pyserial", "install pyserial: `pip install pyserial`", ("serial",)),
)
probe_paramiko = probe_module("paramiko")
probe_pyserial = probe_module("serial")


# ---------------------------------------------------------------- packs


def find_pack_yaml(pack: str) -> Path | None:
    spec = importlib.util.find_spec(f"score.itf.packs.{pack}")
    location = next(iter(spec.submodule_search_locations or ()), None) if spec else None
    candidate = Path(location) / "pack.yaml" if location else None
    return candidate if candidate is not None and candidate.is_file() else None


def prerequisites(pack: str) -> list[str]:
    path = find_pack_yaml(pack)
    if path is None:
        return []
    from score.itf.core.engine.yaml_text import safe_load as yaml_safe_load

    return list((yaml_safe_load(path.read_text(encoding="utf-8")) or {}).get("prerequisites") or ())


def packs_of_target_file(source, overrides=()) -> list[str]:
    """The packs a target file names, from its factory labels (its override files included)."""
    from score.itf.core.frontends import target_file

    return sorted(target_file.packs_of(target_file.load_all(source, overrides)))


# ---------------------------------------------------------------- running


def run_checks(packs: list[str], selected: bool) -> list[tuple[str, str, str, str]]:
    """(status, name, detail, hint) rows; status is ok, FAIL, warn or manual."""
    needed = set(packs)
    rows = []
    checked = set()  # (pack, prerequisite) an automatic check ran for: not listed again as manual
    for check in CHECKS:
        required = bool(needed & set(check.packs))
        if selected and not required:
            continue
        ok, detail = globals()[check.probe]()
        status = "ok" if ok else ("FAIL" if required else "warn")
        rows.append((status, check.name, detail, "" if ok else check.hint))
        checked |= {(pack, item) for pack in check.packs for item in check.covers}
    for pack in packs:
        for item in prerequisites(pack):
            if item.lower().startswith("none") or (pack, item) in checked:
                continue
            rows.append(("manual", f"{pack}: {item}", "", "cannot be tested here; check it yourself"))
    return rows


def _print_rows(rows) -> None:
    for status, name, detail, hint in rows:
        print(f"[{status:^6}] {name}" + (f"  ({detail})" if status == "ok" else ""))
        if detail and status != "ok":
            print(f"           {detail}")
        if hint:
            print(f"           {'fix: ' if status != 'manual' else ''}{hint}")


def _packs_named(args) -> list[str] | None:
    """The packs of the target file `args` names; None (after saying why) when it cannot be read."""
    from score.itf.cli.main import find

    try:
        found = find(args.target_file, args.override)
        return packs_of_target_file(found.target_file, found.overrides)
    except ValueError as exc:
        print(f"itf: {exc}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001  a malformed document is reported, not a traceback
        print(f"itf: cannot read the target file: {type(exc).__name__}: {exc}", file=sys.stderr)
    return None


def cmd_doctor(args) -> int:
    packs = _packs_named(args)
    if packs is None:
        return 2
    rows = run_checks(packs, selected=True)
    print(f"packs: {', '.join(packs) or '(none)'}")
    _print_rows(rows)
    failed = [r for r in rows if r[0] == "FAIL"]
    print(f"\n{len(failed)} required check(s) failed" if failed else "\nno required check failed")
    return 1 if failed else 0
