"""The owner's policy: short statement lists an agent follows and a context freezes.

Four sections hold items of one shape. ``decision`` has the rules for shortlisting
and dismissing, ``eligibility`` the facts employers ask about, ``writing`` the rules
for documents (each with a scope) and ``facts`` everything else the owner confirmed.
Every section has its own version; an item write names the version of its section.

Confirmation is the owner's. A content write (label, statement, value, scope or
rule) by the dashboard session or an owner token confirms the item; the same write
by an agent token leaves it a proposal and switches its rule off. Only owner
authority confirms a proposal or enables a rule.

A decision item may carry a rule on a collection signal. An enabled rule the owner
confirmed acts on new jobs as their signals arrive (job_signals.py).

``PolicyService`` is in service.py; models.py holds the sections, the signal
registry ``SIGNALS`` and the inputs, records.py the records as read and the
frozen policy.
"""

from .models import (
    SECTIONS,
    SIGNALS,
    PolicyItemCreate,
    PolicyItemUpdate,
    PolicyMove,
    PolicyReorder,
    PolicyVersion,
    RulePreview,
    Section,
)
from .records import frozen_policy
from .service import PolicyService

__all__ = [
    "SECTIONS",
    "SIGNALS",
    "PolicyItemCreate",
    "PolicyItemUpdate",
    "PolicyMove",
    "PolicyReorder",
    "PolicyService",
    "PolicyVersion",
    "RulePreview",
    "Section",
    "frozen_policy",
]
