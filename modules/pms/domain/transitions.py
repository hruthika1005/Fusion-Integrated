"""The transition table and engine (blueprint section 5).

One row per (carrier, source states, target, roles, use case, guards). `in_spec_tables` is
False for the three rows (covering four transitions) that BR or UC text states but the
workflow tables omit (blueprint Extra_Transitions X-02, X-03, X-04, X-07). The two deferred
ones (X-05 reassignment after a missed review, X-06 grant recording) are deliberately absent
until decisions D-04 and D-06 are ruled.

`apply` verifies the transition exists, the role may perform it, and every guard the row
lists was reported satisfied by the service. A guard that was not reported fails closed.
"""

from dataclasses import dataclass
from enum import StrEnum

from .errors import Conflict, Forbidden, InvalidState
from .states import (
    ApplicationStatus,
    AttorneyState,
    BudgetOutcome,
    MaintenanceState,
    OfficeActionState,
    Role,
)


class Carrier(StrEnum):
    APPLICATION = "APPLICATION"
    ATTORNEY = "ATTORNEY"
    BUDGET = "BUDGET"
    OFFICE_ACTION = "OFFICE_ACTION"
    MAINTENANCE = "MAINTENANCE"


@dataclass(frozen=True)
class Transition:
    carrier: Carrier
    sources: frozenset
    target: object
    roles: frozenset
    uc: str
    guards: frozenset
    in_spec_tables: bool = True


def _t(carrier, sources, target, roles, uc, guards, in_spec_tables=True):
    return Transition(
        Carrier[carrier],
        frozenset(sources),
        target,
        frozenset(roles),
        uc,
        frozenset(guards),
        in_spec_tables,
    )


TRANSITIONS = (
    _t(
        "APPLICATION",
        [ApplicationStatus.DRAFT],
        ApplicationStatus.SUBMITTED,
        [Role.APPLICANT],
        "UC-PMS-001",
        ["BR-PMS-014", "BR-PMS-015", "BR-PMS-016", "BR-PMS-017"],
    ),
    _t(
        "APPLICATION",
        [ApplicationStatus.NEEDS_REVISION],
        ApplicationStatus.RESUBMITTED,
        [Role.APPLICANT],
        "UC-PMS-005",
        ["BR-PMS-033", "BR-PMS-035", "BR-PMS-036", "BR-PMS-087"],
    ),
    _t(
        "APPLICATION",
        [
            ApplicationStatus.SUBMITTED,
            ApplicationStatus.UNDER_REVIEW,
            ApplicationStatus.NEEDS_REVISION,
            ApplicationStatus.REJECTED,
            ApplicationStatus.APPROVED,
        ],
        ApplicationStatus.WITHDRAWN,
        [Role.APPLICANT],
        "UC-PMS-006",
        ["BR-PMS-067", "BR-PMS-068", "BR-PMS-069", "BR-PMS-070"],
    ),
    _t(
        "APPLICATION",
        [ApplicationStatus.SUBMITTED, ApplicationStatus.RESUBMITTED],
        ApplicationStatus.UNDER_REVIEW,
        [Role.PCC_ADMIN],
        "UC-PMS-007",
        ["BR-PMS-022", "BR-PMS-023", "BR-PMS-024", "BR-PMS-025", "BR-PMS-026", "BR-PMS-027"],
    ),
    _t(
        "APPLICATION",
        [ApplicationStatus.UNDER_REVIEW],
        ApplicationStatus.APPROVED,
        [Role.DIRECTOR],
        "UC-PMS-008",
        ["BR-PMS-029", "BR-PMS-030", "BR-PMS-031"],
    ),
    _t(
        "APPLICATION",
        [ApplicationStatus.UNDER_REVIEW],
        ApplicationStatus.NEEDS_REVISION,
        [Role.DIRECTOR],
        "UC-PMS-008",
        ["BR-PMS-029", "BR-PMS-030", "BR-PMS-031"],
    ),
    _t(
        "APPLICATION",
        [ApplicationStatus.UNDER_REVIEW],
        ApplicationStatus.REJECTED,
        [Role.DIRECTOR],
        "UC-PMS-008",
        ["BR-PMS-029", "BR-PMS-030", "BR-PMS-031"],
    ),
    _t(
        "APPLICATION",
        [ApplicationStatus.APPROVED],
        ApplicationStatus.FILED,
        [Role.ATTORNEY],
        "UC-PMS-013",
        ["BR-PMS-020", "BR-PMS-055", "BR-PMS-056", "BR-PMS-128", "BR-PMS-138", "BR-PMS-142"],
    ),
    _t(
        "APPLICATION",
        [ApplicationStatus.REJECTED],
        ApplicationStatus.APPEAL_SUBMITTED,
        [Role.APPLICANT],
        "UC-PMS-022",
        ["BR-PMS-092", "BR-PMS-093", "BR-PMS-094"],
    ),
    _t(
        "APPLICATION",
        [ApplicationStatus.APPEAL_SUBMITTED],
        ApplicationStatus.REJECTION_UPHELD,
        [Role.DIRECTOR],
        "UC-PMS-023",
        ["BR-PMS-095"],
    ),
    _t(
        "APPLICATION",
        [ApplicationStatus.APPEAL_SUBMITTED],
        ApplicationStatus.REMANDED_FOR_AMENDMENT,
        [Role.DIRECTOR],
        "UC-PMS-023",
        ["BR-PMS-095"],
    ),
    _t(
        "APPLICATION",
        [ApplicationStatus.APPEAL_SUBMITTED],
        ApplicationStatus.DECISION_MODIFIED,
        [Role.DIRECTOR],
        "UC-PMS-023",
        ["BR-PMS-095"],
    ),
    _t(
        "APPLICATION",
        [ApplicationStatus.NEEDS_REVISION, ApplicationStatus.REJECTED],
        ApplicationStatus.EXPIRED,
        [Role.SYSTEM],
        "UC-PMS-005",
        ["BR-PMS-038"],
        in_spec_tables=False,
    ),
    _t(
        "APPLICATION",
        [ApplicationStatus.NEEDS_REVISION, ApplicationStatus.REJECTED],
        ApplicationStatus.EXPIRED,
        [Role.APPLICANT],
        "UC-PMS-005",
        ["BR-PMS-035", "BR-PMS-038"],
        in_spec_tables=False,
    ),
    _t(
        "APPLICATION",
        [ApplicationStatus.REJECTED],
        ApplicationStatus.RESUBMITTED,
        [Role.APPLICANT],
        "UC-PMS-005",
        ["BR-PMS-034", "BR-PMS-035", "BR-PMS-036"],
        in_spec_tables=False,
    ),
    _t(
        "ATTORNEY",
        [AttorneyState.NONE, AttorneyState.DECLINED],
        AttorneyState.OFFERED,
        [Role.PCC_ADMIN],
        "UC-PMS-010",
        [
            "BR-PMS-040",
            "BR-PMS-041",
            "BR-PMS-042",
            "BR-PMS-043",
            "BR-PMS-044",
            "BR-PMS-045",
            "BR-PMS-127",
        ],
    ),
    _t(
        "ATTORNEY",
        [AttorneyState.OFFERED],
        AttorneyState.ASSIGNED,
        [Role.ATTORNEY],
        "UC-PMS-011",
        [],
    ),
    _t(
        "ATTORNEY",
        [AttorneyState.OFFERED],
        AttorneyState.DECLINED,
        [Role.ATTORNEY],
        "UC-PMS-011",
        [],
    ),
    _t(
        "BUDGET",
        [BudgetOutcome.NONE],
        BudgetOutcome.APPROVED,
        [Role.DIRECTOR],
        "UC-PMS-009",
        ["BR-PMS-048", "BR-PMS-049", "BR-PMS-050", "BR-PMS-052", "BR-PMS-053"],
    ),
    _t(
        "BUDGET",
        [BudgetOutcome.NONE],
        BudgetOutcome.REJECTED,
        [Role.DIRECTOR],
        "UC-PMS-009",
        ["BR-PMS-052"],
    ),
    _t(
        "BUDGET",
        [BudgetOutcome.NONE],
        BudgetOutcome.ESCALATED,
        [Role.DIRECTOR],
        "UC-PMS-009",
        ["BR-PMS-051", "BR-PMS-052"],
    ),
    _t(
        "BUDGET",
        [BudgetOutcome.ESCALATED],
        BudgetOutcome.ESCALATION_TRACKED,
        [Role.PCC_ADMIN],
        "UC-PMS-027",
        ["BR-PMS-051"],
    ),
    _t(
        "OFFICE_ACTION",
        [OfficeActionState.NONE],
        OfficeActionState.OFFICE_ACTION_RECORDED,
        [Role.ATTORNEY],
        "UC-PMS-014",
        ["BR-PMS-138", "BR-PMS-142"],
    ),
    _t(
        "OFFICE_ACTION",
        [OfficeActionState.OFFICE_ACTION_RECORDED],
        OfficeActionState.AWAITING_APPLICANT_APPROVAL,
        [Role.ATTORNEY],
        "UC-PMS-015",
        ["BR-PMS-066", "BR-PMS-146"],
    ),
    _t(
        "OFFICE_ACTION",
        [OfficeActionState.OFFICE_ACTION_RECORDED],
        OfficeActionState.RESPONSE_READY,
        [Role.ATTORNEY],
        "UC-PMS-015",
        ["BR-PMS-066", "BR-PMS-146"],
    ),
    _t(
        "OFFICE_ACTION",
        [OfficeActionState.AWAITING_APPLICANT_APPROVAL],
        OfficeActionState.APPLICANT_APPROVED,
        [Role.APPLICANT],
        "UC-PMS-029",
        ["BR-PMS-146"],
    ),
    _t(
        "OFFICE_ACTION",
        [OfficeActionState.APPLICANT_APPROVED, OfficeActionState.RESPONSE_READY],
        OfficeActionState.RESPONSE_SUBMITTED,
        [Role.ATTORNEY],
        "UC-PMS-015",
        ["BR-PMS-065", "BR-PMS-066"],
    ),
    _t(
        "MAINTENANCE",
        [MaintenanceState.MAINTENANCE_ACTIVE],
        MaintenanceState.RENEWAL_DECISION_REQUESTED,
        [Role.ATTORNEY],
        "UC-PMS-017",
        ["BR-PMS-059", "BR-PMS-060", "BR-PMS-061"],
    ),
    _t(
        "MAINTENANCE",
        [MaintenanceState.RENEWAL_DECISION_REQUESTED],
        MaintenanceState.RENEWAL_APPROVED,
        [Role.DIRECTOR],
        "UC-PMS-018",
        ["BR-PMS-061"],
    ),
    _t(
        "MAINTENANCE",
        [MaintenanceState.RENEWAL_DECISION_REQUESTED],
        MaintenanceState.DO_NOT_RENEW,
        [Role.DIRECTOR],
        "UC-PMS-018",
        ["BR-PMS-061"],
    ),
    _t(
        "MAINTENANCE",
        [MaintenanceState.RENEWAL_APPROVED],
        MaintenanceState.RENEWED,
        [Role.ATTORNEY],
        "UC-PMS-017",
        ["BR-PMS-060"],
    ),
)


def find(carrier, source, target):
    """All table rows for this carrier going from `source` to `target`."""
    return [
        t
        for t in TRANSITIONS
        if t.carrier == carrier and source in t.sources and t.target == target
    ]


def apply(carrier, source, target, role, satisfied_guards=frozenset(), uc=None,
          system_context=False):
    """Validate a transition and return its row; raises a DomainError otherwise.

    Order: the transition must exist (409), the role must be allowed (403), and every guard
    must be reported satisfied (409). `uc` narrows the match when two rows share the endpoints.

    The SYSTEM role is for scheduled jobs only. It is refused unless the caller passes
    `system_context=True`, so a role parsed from a request can never expire an application.
    """
    try:
        role = Role(role)
    except ValueError:
        raise Forbidden("ROLE_NOT_PERMITTED", "Unknown role.") from None
    if role == Role.SYSTEM and not system_context:
        raise Forbidden("SYSTEM_ROLE_REQUIRES_TRUSTED_CONTEXT",
                        "The system role may only be used by trusted jobs.")
    rows = [t for t in find(carrier, source, target) if uc is None or t.uc == uc]
    if not rows:
        raise InvalidState(
            "TRANSITION_NOT_ALLOWED",
            f"{carrier.value}: {getattr(source, 'value', source)} to "
            f"{getattr(target, 'value', target)} is not a permitted transition.",
        )
    permitted = [t for t in rows if role in t.roles]
    if not permitted:
        raise Forbidden("ROLE_NOT_PERMITTED", "This role may not perform that transition.")
    row = permitted[0]
    missing = sorted(row.guards - set(satisfied_guards))
    if missing:
        raise Conflict(
            "GUARD_NOT_SATISFIED",
            "A business-rule guard was not satisfied.",
            {"missing_guards": missing},
        )
    return row


def allowed_targets(carrier, source, role):
    """Targets this role could move to from `source` (for server-provided allowed actions)."""
    return sorted(
        {
            t.target
            for t in TRANSITIONS
            if t.carrier == carrier and source in t.sources and role in t.roles
        },
        key=lambda s: s.value,
    )


__all__ = [
    "TRANSITIONS",
    "ApplicationStatus",
    "AttorneyState",
    "BudgetOutcome",
    "Carrier",
    "MaintenanceState",
    "OfficeActionState",
    "Role",
    "Transition",
    "allowed_targets",
    "apply",
    "find",
]
