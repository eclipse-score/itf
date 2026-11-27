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
"""Gate 1 — what must exist. Pick one winning declaration per node name, choose its provider, fill
each of the provider's slots (explicit bind, else the single candidate in scope, else the slot is
unsatisfied), check shapes at every seam, and order construction. Reads kind flags, never kind names.
"""

from .claims import (  # noqa: F401
    BindingClaim,
    CapabilityContractClaim,
    NodeClaim,
    ProviderClaim,
    ShapeExpectationClaim,
)
from .plan import (  # noqa: F401
    PlannedNode,
    TargetPlan,
)
from .resolve import (  # noqa: F401
    resolve_contract_to_node,
)
from .kind import (  # noqa: F401
    CAPABILITY,
    CLAIM_TYPES,
    CODES,
    RELATION,
)
