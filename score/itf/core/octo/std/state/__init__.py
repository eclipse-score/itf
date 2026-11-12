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
"""Gate 2 — what must happen. From the goal states, pick the steps that deliver them (and what those
require), drop what is already observed, then order the steps so every state is still true when
something needs it: producers before consumers, destroyers before the producer they would undo.
Observed facts have probe evidence; assumed facts suppress producers too, but remain explicit in
the returned plan so callers can distinguish assertion from observation.
"""

from .claims import (  # noqa: F401
    AssumeClaim,
    GoalClaim,
    RelationClaim,
    StateContractClaim,
)
from .plan import (  # noqa: F401
    ActionPlan,
    PlannedStep,
)
from .resolve import (  # noqa: F401
    resolve_condition_to_producer,
    use_candidates,
)
from .kind import (  # noqa: F401
    CLAIM_TYPES,
    CODES,
    RELATION,
    STATE,
)
