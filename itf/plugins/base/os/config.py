# *******************************************************************************
# Copyright (c) 2025 Contributors to the Eclipse Foundation
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
# pylint: disable=invalid-name
from itf.plugins.utils.bunch import Bunch


DIAGNOSTICS_COMMON = {
    "df_h": {
        "description": "Disk usage",
        "command": "df -h",
    },
    "ls_l_dev": {
        "description": "List devices",
        "command": "ls -l /dev/",
    },
    "netstat_r": {
        "description": "Networking status - routing",
        "command": "netstat -r",
    },
}


DIAGNOSTICS_LINUX = {
    "ps_aux": {
        "description": "Processes - currently running",
        "command": "ps aux",
    },
    "top_b_n_1": {
        "description": "Processes - resources consumption",
        "command": "top -b -n 1",
    },
    "journalctl": {
        "description": "Query the systemd journal",
        "command": "journalctl",
    },
    "netstat_tul": {
        "description": "Networking status - TCP/UDP Listening Ports",
        "command": "netstat -tul",
    },
    "netstat_xln": {
        "description": "Networking status - active Unix domain sockets",
        "command": "netstat -xln",
    },
    "ip_a": {
        "description": "Networking status - interfaces",
        "command": "ip a",
    },
    "iptables_L": {
        "description": "Firewall rules",
        "command": "iptables -S",
    },
    "systemd_analyze_plot": {
        "description": "Systemd startup time plot",
        "command": "systemd-analyze plot",
        "extension": "svg",
    },
}
DIAGNOSTICS_LINUX.update(DIAGNOSTICS_COMMON)


DIAGNOSTICS_QNX = {
    "ps_A": {
        "description": "Processes - currently running",
        "command": "ps -A",
    },
    "top_i_1": {
        "description": "Processes - resources consumption",
        "command": "top -b -i 1",
    },
    "netstat": {
        "description": "Networking status - active Unix domain, IPv4 and IPv6 sockets",
        "command": "netstat",
    },
}
DIAGNOSTICS_QNX.update(DIAGNOSTICS_COMMON)


def os_config(name, diagnostics, ssh_uses_ext_ip):
    return Bunch(
        name=name,
        diagnostics=diagnostics,
        ssh_uses_ext_ip=ssh_uses_ext_ip,
    )


operating_system = Bunch(
    linux=os_config("linux", DIAGNOSTICS_LINUX, False),
    qnx=os_config("qnx", DIAGNOSTICS_QNX, False),
)


global_os_config = Bunch(
    os=operating_system,
)
