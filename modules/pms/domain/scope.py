"""Record-scope predicates (BR-003, BR-005, BR-006, BR-026, BR-027, BR-130).

Services call these in selectors and before every write, so a record outside a caller's scope
is not found (404) rather than forbidden. Pure functions with no database access.
"""


def applicant_owns(owner_user_id, user_id):
    """BR-003: an Applicant sees only their own applications."""
    return user_id is not None and owner_user_id == user_id


def director_in_scope(director_domains, application_domain, is_assigned_reviewer, conflicted):
    """A Director sees an application they are assigned to review, or one in a domain of their
    expertise (BR-005, BR-006). A Director listed as an inventor has no Director scope over it
    (BR-026).
    """
    if conflicted:
        return False
    if is_assigned_reviewer:
        return True
    return application_domain is not None and application_domain in director_domains


def attorney_in_scope(is_assigned_attorney, conflicted):
    """An Attorney sees only applications they are assigned to, unless listed as inventor."""
    return bool(is_assigned_attorney) and not conflicted


def can_act_as_reviewer(conflicted):
    """BR-026, BR-027: a Director or PCC_ADMIN listed as an inventor may not review."""
    return not conflicted
