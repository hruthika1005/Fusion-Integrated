"""Structured domain errors suitable for API mapping."""
class DomainError(Exception):
    KIND_VALIDATION="validation"
    KIND_FORBIDDEN="forbidden"
    KIND_CONFLICT="conflict"
    KIND_CONFIG="configuration"
    def __init__(self, code, message, details=None, status=400):
        super().__init__(message); self.kind=(self.KIND_VALIDATION if status==422 else self.KIND_FORBIDDEN if status==403 else self.KIND_CONFLICT if status==409 else self.KIND_CONFIG if status==500 else "domain"); self.code=code; self.message=message; self.details=details or {}; self.status=status
class ValidationFailed(DomainError):
    def __init__(self, code, message, details=None): super().__init__(code,message,details,422)
class Unprocessable(DomainError):
    def __init__(self, code, message, details=None): super().__init__(code,message,details,422)
class Forbidden(DomainError):
    def __init__(self, code='FORBIDDEN', message='Action is not permitted.', details=None): super().__init__(code,message,details,403)
class Conflict(DomainError):
    def __init__(self, code='CONFLICT', message='Conflict.', details=None): super().__init__(code,message,details,409)
class InvalidState(Conflict):
    def __init__(self, code='INVALID_STATE', message='Invalid state for this operation.', details=None): super().__init__(code,message,details)
class ConfigRequired(DomainError):
    def __init__(self, code='CONFIG_REQUIRED', message='Required configuration is missing.', details=None): super().__init__(code,message,details,500)
