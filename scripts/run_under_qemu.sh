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

#!/bin/bash
set -euo pipefail

# Check if TEST_UNDECLARED_OUTPUTS_DIR is set
CMD_UNDECLARED_OUTPUTS_DIR="true"
if [[ -n "${TEST_UNDECLARED_OUTPUTS_DIR:-}" ]]; then
	CMD_UNDECLARED_OUTPUTS_DIR="export TEST_UNDECLARED_OUTPUTS_DIR=$TEST_UNDECLARED_OUTPUTS_DIR"
else
	TEST_UNDECLARED_OUTPUTS_DIR="/tmp"
fi

# Create a temp directory to be mounted as /var/run inside the unshared user namespace
TMP_VAR_RUN_DIR=${TEST_TMPDIR-$(mktemp -d)}/tmp_var_run
mkdir -p "${TMP_VAR_RUN_DIR}"
CMD_CREATE_VAR_DIR="mount --bind $TMP_VAR_RUN_DIR /var/run"

# CMD_BRIDGE_NETWORK="ip link add name virbr0 type bridge &&
# ip link set virbr0 up &&
# ip addr add 192.168.122.1/24 dev virbr0"

# CMD_ENABLE_IP_FORWARDING="echo 1 | tee /proc/sys/net/ipv4/ip_forward"

# Creates a new tap device using tunctl. Afterwards it configures the new network interface with
# the correct ip-address and the correct routing information.
CMD_TAP0_INTERFACE="ip tuntap add mode tap tap0 &&
ip addr add 169.254.21.88/16 broadcast 160.48.199.255 dev tap0 &&
ip link set dev tap0 up &&
ip link add link tap0 name tap0.73 type vlan id 73 &&
ip addr add 160.48.199.77/25 broadcast 160.48.199.255 dev tap0.73 &&
ip link set dev tap0.73 up &&
ip link set tap0.73 multicast on &&
ip route add 231.255.42.99 dev tap0.73 &&
ip route add 232.255.42.99 dev tap0.73 &&
ip route add 233.255.42.99 dev tap0.73 &&
ip route add 234.255.42.99 dev tap0.73 &&
ip route add 235.255.42.99 dev tap0.73 &&
ip route add 236.255.42.99 dev tap0.73 &&
ip route add 237.255.42.99 dev tap0.73 &&
ip route add 239.255.42.99 dev tap0.73 &&
ip link add link tap0 name tap0.105 type vlan id 105 &&
ip addr add 160.48.249.142/27 broadcast 160.48.249.255 dev tap0.105 &&
ip link set dev tap0.105 up &&
ip link set tap0.105 multicast on &&
ip route add 224.0.0.0/4 dev tap0 &&
ip route append 224.0.0.0/4 dev tap0.73 &&
ip route append 224.0.0.0/4 dev tap0.105"

CMD_TAP1_INTERFACE="ip tuntap add mode tap tap1 &&
ip addr add 192.168.1.99/24 broadcast 160.48.199.255 dev tap1 &&
ip link set dev tap1 up &&
ip route add to 192.168.1.99 dev tap1"

# Allow non-root user to bind to port 500
# CMD_UNPRIVILEGED_PORT_START_500="echo 500 | tee /proc/sys/net/ipv4/ip_unprivileged_port_start"

# Run the concatenated commands in an unnamed network namespace for isolation
unshare -m -U -n --map-root-user /bin/bash -c \
  "${CMD_UNDECLARED_OUTPUTS_DIR} &&
  ${CMD_CREATE_VAR_DIR} &&
  ${CMD_TAP0_INTERFACE} &&
  ${CMD_TAP1_INTERFACE} &&
  ${*}"
