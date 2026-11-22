from .errors import Forbidden, Conflict, InvalidState
from .states import Role, ApplicationStatus, AttorneyState
def require_pcc_admin(role):
 if role!=Role.PCC_ADMIN: raise Forbidden('PCC_ADMIN_REQUIRED','Only PCC_ADMIN may assign Attorneys.')
def require_approved(status):
 if status!=ApplicationStatus.APPROVED: raise InvalidState('NOT_APPROVED','Attorney assignment requires Approved status.')
def require_panel_or_exception(in_panel,has_exception):
 if not in_panel and not has_exception: raise Conflict('NOT_IN_PANEL','Attorney is not on the approved panel and has no exception.')
def require_no_open_assignment(state):
 if state in (AttorneyState.OFFERED,AttorneyState.ASSIGNED): raise Conflict('OPEN_ASSIGNMENT','Attorney already has an open assignment.')
