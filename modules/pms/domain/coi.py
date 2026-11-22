from dataclasses import dataclass
@dataclass(frozen=True)
class ListedInventor:
 user_id: int|None=None
 email: str|None=None
def is_conflicted(user_id, email, inventors):
 norm=(email or '').strip().lower()
 for i in inventors or []:
  if user_id is not None and i.user_id is not None and user_id==i.user_id: return True
  if user_id is not None and i.user_id is None and norm and norm==(i.email or '').strip().lower(): return True
 return False
