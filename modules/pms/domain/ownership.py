from decimal import Decimal, InvalidOperation
from .errors import ValidationFailed
def validate_shares(shares):
 if not shares: raise ValidationFailed('OWNERSHIP_REQUIRED','Inventor ownership shares are required.')
 vals=[]
 for x in shares:
  try: d=Decimal(str(x))
  except (InvalidOperation,ValueError,TypeError): raise ValidationFailed('INVALID_SHARE','Ownership share must be numeric.') from None
  if not d.is_finite() or d<0 or d>100: raise ValidationFailed('INVALID_SHARE','Ownership shares must be between 0 and 100.')
  vals.append(d)
 if sum(vals)!=Decimal('100'): raise ValidationFailed('OWNERSHIP_TOTAL','Ownership shares must total 100%.',{'total':str(sum(vals))})
 return vals
