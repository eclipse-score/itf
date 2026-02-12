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

CMD_LO_INTERFACE="\
ip link set lo up"

# Creates a new tap device. Afterwards it configures the new network interface with
# the correct ip-address.
CMD_TAP0_INTERFACE="\
ip tuntap add mode tap tap0 &&
ip addr add 169.254.21.88/16 broadcast 160.48.199.255 dev tap0 &&
ip link set dev tap0 up"

# Run the concatenated commands in an unnamed network namespace for isolation
unshare -m -U -n --map-root-user /bin/bash -c \
  "${CMD_UNDECLARED_OUTPUTS_DIR} &&
  ${CMD_CREATE_VAR_DIR} &&
  ${CMD_LO_INTERFACE} &&
  ${CMD_TAP0_INTERFACE} &&
  ${*}"
