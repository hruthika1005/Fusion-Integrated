from functools import wraps
from core.api.exceptions import ConflictError, BadRequestError, PermissionDeniedError
from modules.pms.domain.errors import DomainError

def translate(fn):
    @wraps(fn)
    def inner(*args,**kwargs):
        try:return fn(*args,**kwargs)
        except DomainError as exc:
            if exc.status==403:raise PermissionDeniedError(exc.message,code=exc.code,details=exc.details)
            if exc.status==409:raise ConflictError(exc.message,code=exc.code,details=exc.details)
            raise BadRequestError(exc.message,code=exc.code,details=exc.details)
    return inner
