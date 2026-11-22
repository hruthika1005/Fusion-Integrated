from .states import Role, ApplicationStatus, AttorneyState
def can_edit_documents(role,is_owner,status): return role==Role.APPLICANT and is_owner and status==ApplicationStatus.NEEDS_REVISION
def can_upload(role,is_owner,is_assigned,status,attorney_state=AttorneyState.NONE):
 if role==Role.APPLICANT: return is_owner and status in (ApplicationStatus.DRAFT,ApplicationStatus.NEEDS_REVISION)
 if role==Role.ATTORNEY: return is_assigned and (attorney_state==AttorneyState.ASSIGNED or status==ApplicationStatus.FILED)
 return False
def can_read(role,is_owner,is_assigned,status,classification='CONFIDENTIAL',previous_version=None):
 if role==Role.APPLICANT: return is_owner and (status==ApplicationStatus.NEEDS_REVISION if previous_version is not None else status not in (ApplicationStatus.DRAFT,))
 if role==Role.DIRECTOR: return is_assigned
 if role==Role.PCC_ADMIN: return classification != "RESTRICTED"
 if role==Role.ATTORNEY: return is_assigned
 return False
