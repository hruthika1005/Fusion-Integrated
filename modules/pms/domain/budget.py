"""Budget rules (BR-048..BR-053). Above the threshold the result is Escalated and the
Director records no outcome (UC-009 step 4, A-48). A total equal to the threshold is within it.
"""
from decimal import Decimal

from .errors import ConfigRequired, InvalidState, ValidationFailed
from .states import ApplicationStatus, BudgetOutcome
from .validators import require_decimal


def validate_components(filing_fees, attorney_fees, administrative_costs):
    """BR-048, BR-049, BR-050: each component is required and not negative."""
    values, missing = {}, []
    for name, raw in (("filing_fees", filing_fees), ("attorney_fees", attorney_fees),
                      ("administrative_costs", administrative_costs)):
        if raw is None or str(raw).strip() == "":
            missing.append(name)
            continue
        number = require_decimal(raw, name)
        if number < 0:
            raise ValidationFailed("NEGATIVE_AMOUNT", f"{name} cannot be negative.",
                                   {"rule": "BR-PMS-048", "field": name})
        values[name] = number
    if missing:
        raise ValidationFailed("BUDGET_COMPONENT_MISSING", "All cost components are required.",
                               {"rule": "BR-PMS-048", "missing": missing})
    return values["filing_fees"], values["attorney_fees"], values["administrative_costs"]


def total_cost(filing_fees, attorney_fees, administrative_costs):
    return filing_fees + attorney_fees + administrative_costs


def exceeds_threshold(total, threshold):
    """BR-051. An unset threshold refuses the decision (A-17)."""
    if threshold is None:
        raise ConfigRequired("budget.escalation_threshold")
    try:
        limit = Decimal(str(threshold))
    except ArithmeticError:
        limit = None
    if limit is None or not limit.is_finite() or limit < 0:
        raise ConfigRequired("budget.escalation_threshold",
                             "Configuration value 'budget.escalation_threshold' is not a "
                             "valid amount.")
    return total > limit


def require_approved_status(status):
    """BR-052: literal Application.status == Approved (decision D-02)."""
    if status != ApplicationStatus.APPROVED:
        raise InvalidState("NOT_APPROVED", "Budget decisions need an Approved application.",
                           {"rule": "BR-PMS-052", "status": getattr(status, "value", status)})


def decide(total, threshold, requested):
    """The recorded outcome: Escalated above the threshold, else the Director's choice."""
    if exceeds_threshold(total, threshold):
        return BudgetOutcome.ESCALATED
    if requested not in (BudgetOutcome.APPROVED, BudgetOutcome.REJECTED,
                         BudgetOutcome.APPROVED.value, BudgetOutcome.REJECTED.value):
        raise ValidationFailed("INVALID_BUDGET_OUTCOME", "Outcome must be Approve or Reject.",
                               {"rule": "BR-PMS-051"})
    return BudgetOutcome(requested)


def check_availability(available):
    """BR-053: applies only when availability data exists (None means no data)."""
    if available is False:
        raise InvalidState("BUDGET_NOT_AVAILABLE", "Budget is not available.",
                           {"rule": "BR-PMS-053"})
