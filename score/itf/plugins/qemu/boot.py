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
import logging

logger = logging.getLogger(__name__)


def boot_until_ready(target, max_attempts: int, run_checks):
    """Run the pre-test checks, rebooting the guest if its kernel panicked while booting.

    Only guest kernel panics are retried. Any other failure is raised immediately.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            run_checks(target)
            return
        except Exception:
            if not target.guest_panicked or attempt == max_attempts:
                raise
            logger.warning(f"Guest kernel panicked during boot (attempt {attempt}/{max_attempts}), restarting QEMU")
            target.restart()
