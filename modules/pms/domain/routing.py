from dataclasses import dataclass
from .errors import Unprocessable
@dataclass(frozen=True)
class DirectorCandidate:
 user_id:int; domains:frozenset=frozenset(); active_load:int=0; conflicted:bool=False
@dataclass(frozen=True)
class AttorneyCandidate:
 user_id:int; domains:frozenset=frozenset(); active_load:int=0; in_panel:bool=False; has_exception:bool=False; conflicted:bool=False; preferred:bool=False

def rank_directors(candidates, domain):
 eligible=[c for c in candidates if not c.conflicted and (domain is None or domain in c.domains)]
 return sorted(eligible,key=lambda c:(c.active_load,c.user_id))
def require_director(candidates,domain):
 ranked=rank_directors(candidates,domain)
 if not ranked: raise Unprocessable('NO_ELIGIBLE_DIRECTOR','No eligible Director is available.')
 return ranked
def rank_attorneys(candidates,domain):
 eligible=[c for c in candidates if not c.conflicted and (c.in_panel or c.has_exception)]
 return sorted(eligible,key=lambda c:(0 if c.preferred and c.in_panel else 1,0 if domain and domain in c.domains else 1,c.active_load,c.user_id))
def require_attorney(candidates,domain):
 ranked=rank_attorneys(candidates,domain)
 if not ranked: raise Unprocessable('NO_ELIGIBLE_ATTORNEY','No eligible Attorney is available.')
 return ranked[0]
