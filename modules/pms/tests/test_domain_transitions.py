"""Conformance of the transition table with the specification's 77 workflow rows, plus
invalid-transition, role and guard failure scenarios (blueprint section 5; D-02)."""
import json
import pathlib

import pytest

from modules.pms.domain import transitions as tr
from modules.pms.domain.errors import Conflict, Forbidden, InvalidState
from modules.pms.domain.states import (
    ApplicationStatus as S,
)
from modules.pms.domain.states import (
    AttorneyState as T,
)
from modules.pms.domain.states import (
    BudgetOutcome as B,
)
from modules.pms.domain.states import (
    MaintenanceState as M,
)
from modules.pms.domain.states import (
    OfficeActionState as O,
)
from modules.pms.domain.states import (
    Role,
)
from modules.pms.domain.transitions import Carrier

FIX = pathlib.Path(__file__).parent / "fixtures" / "spec_transitions.json"
SPEC_ROWS = json.loads(FIX.read_text())
ROLE = {"Applicant": Role.APPLICANT, "Director": Role.DIRECTOR, "PCC_ADMIN": Role.PCC_ADMIN,
        "Attorney": Role.ATTORNEY}
APP = {"Draft / Not Submitted": S.DRAFT, "Submitted": S.SUBMITTED, "Under Review": S.UNDER_REVIEW,
       "Approved": S.APPROVED, "Needs Revision": S.NEEDS_REVISION, "Resubmitted": S.RESUBMITTED,
       "Rejected": S.REJECTED, "Appeal Submitted": S.APPEAL_SUBMITTED,
       "Rejection Upheld": S.REJECTION_UPHELD, "Remanded for Amendment": S.REMANDED_FOR_AMENDMENT,
       "Decision Modified": S.DECISION_MODIFIED, "Filed": S.FILED, "Withdrawn": S.WITHDRAWN,
       "Pre-Filing Preconditions Satisfied": S.APPROVED}
# Withdrawal sources "Attorney Assigned" and "Pending Review" are Approved plus the attorney
# track (decision D-02), so they map to Application.status Approved.
WITHDRAW_EXTRA = {"Attorney Assigned": S.APPROVED, "Pending Review": S.APPROVED}
ELIGIBLE = [S.SUBMITTED, S.UNDER_REVIEW, S.NEEDS_REVISION, S.REJECTED, S.APPROVED]


def uc(row):
    return row["uc"].split(" / ")[0]


def resolve(row):
    """Spec row -> list of (carrier, source, target) in the blueprint's model."""
    u, frm, to = uc(row), row["frm"], row["to"]
    if u in ("UC-PMS-001", "UC-PMS-005", "UC-PMS-007", "UC-PMS-008", "UC-PMS-013",
             "UC-PMS-022", "UC-PMS-023"):
        return [(Carrier.APPLICATION, APP[frm], APP[to])]
    if u == "UC-PMS-006":
        if frm.startswith("Any configured"):
            return [(Carrier.APPLICATION, s, S.WITHDRAWN) for s in ELIGIBLE]
        return [(Carrier.APPLICATION, APP.get(frm) or WITHDRAW_EXTRA[frm], S.WITHDRAWN)]
    if u == "UC-PMS-010":
        return [(Carrier.ATTORNEY, T.NONE if frm == "Approved" else T.DECLINED, T.OFFERED)]
    if u == "UC-PMS-011":
        return [(Carrier.ATTORNEY, T.OFFERED,
                 T.ASSIGNED if to == "Attorney Assigned" else T.DECLINED)]
    if u == "UC-PMS-009":
        target = {"Budget Approved": B.APPROVED, "Budget Rejected": B.REJECTED,
                  "Escalated": B.ESCALATED}[to]
        return [(Carrier.BUDGET, B.NONE, target)]
    if u == "UC-PMS-027":
        return [(Carrier.BUDGET, B.ESCALATED, B.ESCALATION_TRACKED)]
    oa = {"Office Action Recorded": O.OFFICE_ACTION_RECORDED,
          "Awaiting Applicant Approval": O.AWAITING_APPLICANT_APPROVAL,
          "Applicant Approved": O.APPLICANT_APPROVED, "Response Ready": O.RESPONSE_READY,
          "Response Submitted": O.RESPONSE_SUBMITTED}
    if u == "UC-PMS-014":
        return [(Carrier.OFFICE_ACTION, O.NONE, oa[to])]
    if u in ("UC-PMS-015", "UC-PMS-029"):
        return [(Carrier.OFFICE_ACTION, oa[frm], oa[to])]
    mt = {"Granted / Maintenance Cycle Active": M.MAINTENANCE_ACTIVE,
          "Renewal Decision Requested": M.RENEWAL_DECISION_REQUESTED,
          "Renewal Approved": M.RENEWAL_APPROVED, "Do Not Renew": M.DO_NOT_RENEW,
          "Renewed / Next Cycle Scheduled": M.RENEWED}
    return [(Carrier.MAINTENANCE, mt[frm], mt[to])]


def row_id(row):
    return f"{row['wf']}#{row['n']:02d}"


def test_fixture_has_all_77_spec_rows():
    assert len(SPEC_ROWS) == 77
    assert sum(1 for r in SPEC_ROWS if r["wf"].startswith("BW")) == 40
    assert sum(1 for r in SPEC_ROWS if r["wf"].startswith("CW")) == 37
    assert len({r["wf"] for r in SPEC_ROWS}) == 21


@pytest.mark.parametrize("row", SPEC_ROWS, ids=row_id)
def test_spec_row_is_allowed_for_its_actor_with_its_guards(row):
    for carrier, source, target in resolve(row):
        # The engine requires the union of BRs the specification cites for this use case and
        # target, so every BR this row cites is in the guard set, and satisfying the whole
        # set permits the transition.
        listed = next(r for r in tr.find(carrier, source, target) if r.uc == uc(row))
        assert set(row["brs"]) <= listed.guards
        found = tr.apply(carrier, source, target, ROLE[row["actor"]], listed.guards,
                         uc=uc(row))
        assert found.uc == uc(row)


@pytest.mark.parametrize("row", SPEC_ROWS, ids=row_id)
def test_spec_row_refused_for_every_other_role(row):
    others = set(Role) - {ROLE[row["actor"]]}
    for carrier, source, target in resolve(row):
        for role in others:
            with pytest.raises(Forbidden):
                tr.apply(carrier, source, target, role, frozenset(row["brs"]), uc=uc(row))


@pytest.mark.parametrize("row", [r for r in SPEC_ROWS if r["brs"]], ids=row_id)
def test_spec_row_refused_when_any_guard_missing(row):
    for carrier, source, target in resolve(row):
        for guard in row["brs"]:
            satisfied = frozenset(row["brs"]) - {guard}
            with pytest.raises(Conflict) as err:
                tr.apply(carrier, source, target, ROLE[row["actor"]], satisfied, uc=uc(row))
            assert guard in err.value.details["missing_guards"]


def test_every_table_row_is_reachable_from_a_spec_row_or_flagged_extra():
    covered = set()
    for row in SPEC_ROWS:
        for carrier, source, target in resolve(row):
            for found in tr.find(carrier, source, target):
                if found.uc == uc(row):
                    covered.add(found)
    uncovered = [t for t in tr.TRANSITIONS if t not in covered]
    assert uncovered
    assert all(not t.in_spec_tables for t in uncovered)
    assert len(uncovered) == 3


class TestInvalidTransitions:
    def test_cannot_skip_review(self):
        with pytest.raises(InvalidState) as err:
            tr.apply(Carrier.APPLICATION, S.SUBMITTED, S.APPROVED, Role.DIRECTOR)
        assert err.value.code == "TRANSITION_NOT_ALLOWED"

    @pytest.mark.parametrize("source", [S.WITHDRAWN, S.EXPIRED, S.FILED, S.REJECTION_UPHELD])
    def test_terminal_states_cannot_withdraw(self, source):
        with pytest.raises(InvalidState):
            tr.apply(Carrier.APPLICATION, source, S.WITHDRAWN, Role.APPLICANT)

    def test_filed_application_cannot_be_withdrawn(self):  # BR-067
        rows = [t for t in tr.TRANSITIONS if t.target == S.WITHDRAWN]
        assert rows
        assert all(S.FILED not in t.sources for t in rows)

    def test_applicant_cannot_approve_own_application(self):
        with pytest.raises(Forbidden):
            tr.apply(Carrier.APPLICATION, S.UNDER_REVIEW, S.APPROVED, Role.APPLICANT,
                     frozenset({"BR-PMS-029", "BR-PMS-030", "BR-PMS-031"}))

    def test_director_cannot_assign_attorney(self):  # BR-040
        with pytest.raises(Forbidden):
            tr.apply(Carrier.ATTORNEY, T.NONE, T.OFFERED, Role.DIRECTOR,
                     frozenset({"BR-PMS-040"}))

    def test_attorney_assignment_does_not_change_application_status(self):  # D-02
        assert all(t.carrier != Carrier.APPLICATION or t.target not in
                   {getattr(S, "ATTORNEY_ASSIGNED", None), getattr(S, "PENDING_REVIEW", None)}
                   for t in tr.TRANSITIONS)
        assert not hasattr(S, "ATTORNEY_ASSIGNED")
        assert not hasattr(S, "PENDING_REVIEW")

    def test_no_second_offer_state_machine_hole(self):
        with pytest.raises(InvalidState):
            tr.apply(Carrier.ATTORNEY, T.ASSIGNED, T.OFFERED, Role.PCC_ADMIN)

    def test_reassignment_possible_only_after_decline(self):
        tr.apply(Carrier.ATTORNEY, T.DECLINED, T.OFFERED, Role.PCC_ADMIN,
                 frozenset(tr.find(Carrier.ATTORNEY, T.DECLINED, T.OFFERED)[0].guards))

    def test_budget_decides_once_and_escalation_has_no_onward_approval(self):  # D-08
        assert tr.find(Carrier.BUDGET, B.APPROVED, B.APPROVED) == []
        assert tr.find(Carrier.BUDGET, B.ESCALATION_TRACKED, B.APPROVED) == []
        assert tr.find(Carrier.BUDGET, B.ESCALATED, B.APPROVED) == []

    def test_budget_and_attorney_tracks_are_independent(self):  # CW-02, AFR-227
        tr.apply(Carrier.BUDGET, B.NONE, B.APPROVED, Role.DIRECTOR,
                 frozenset(tr.find(Carrier.BUDGET, B.NONE, B.APPROVED)[0].guards))
        tr.apply(Carrier.ATTORNEY, T.NONE, T.OFFERED, Role.PCC_ADMIN,
                 frozenset(tr.find(Carrier.ATTORNEY, T.NONE, T.OFFERED)[0].guards))

    def test_office_action_cannot_submit_without_applicant_approval(self):  # BR-146
        with pytest.raises(InvalidState):
            tr.apply(Carrier.OFFICE_ACTION, O.AWAITING_APPLICANT_APPROVAL,
                     O.RESPONSE_SUBMITTED, Role.ATTORNEY, frozenset({"BR-PMS-065"}))

    def test_unapproved_maintenance_action_refused(self):  # BR-061
        with pytest.raises(InvalidState):
            tr.apply(Carrier.MAINTENANCE, M.RENEWAL_DECISION_REQUESTED, M.RENEWED,
                     Role.ATTORNEY, frozenset({"BR-PMS-060"}))

    def test_deferred_transitions_are_not_in_the_table(self):  # X-05, X-06 (D-04, D-06)
        assert tr.find(Carrier.APPLICATION, S.UNDER_REVIEW, S.UNDER_REVIEW) == []
        assert not any(t.uc == "UC-PMS-017" and t.carrier == Carrier.APPLICATION
                       for t in tr.TRANSITIONS)

    def test_one_traversal_loops_are_not_capped(self):  # A-32
        for _ in range(3):
            tr.apply(Carrier.APPLICATION, S.UNDER_REVIEW, S.NEEDS_REVISION, Role.DIRECTOR,
                     frozenset({"BR-PMS-029", "BR-PMS-030", "BR-PMS-031"}))
            tr.apply(Carrier.APPLICATION, S.NEEDS_REVISION, S.RESUBMITTED, Role.APPLICANT,
                     frozenset(tr.find(Carrier.APPLICATION, S.NEEDS_REVISION, S.RESUBMITTED)
                               [0].guards))
            tr.apply(Carrier.APPLICATION, S.RESUBMITTED, S.UNDER_REVIEW, Role.PCC_ADMIN,
                     frozenset(tr.find(Carrier.APPLICATION, S.RESUBMITTED, S.UNDER_REVIEW)
                               [0].guards))


class TestExtraTransitions:
    def test_late_attempt_and_job_set_expired(self):  # BR-038, UC-005 exception
        for role in (Role.SYSTEM, Role.APPLICANT):
            for src in (S.NEEDS_REVISION, S.REJECTED):
                row = next(t for t in tr.find(Carrier.APPLICATION, src, S.EXPIRED)
                           if role in t.roles)
                tr.apply(Carrier.APPLICATION, src, S.EXPIRED, role, row.guards,
                         system_context=True)

    def test_revision_from_rejected_is_unconditional_and_flagged(self):  # BR-034, C-02
        row = tr.find(Carrier.APPLICATION, S.REJECTED, S.RESUBMITTED)[0]
        assert not row.in_spec_tables
        assert "BR-PMS-034" in row.guards
        tr.apply(Carrier.APPLICATION, S.REJECTED, S.RESUBMITTED, Role.APPLICANT, row.guards)


class TestAllowedTargets:
    def test_director_from_under_review(self):
        assert [t.value for t in tr.allowed_targets(
            Carrier.APPLICATION, S.UNDER_REVIEW, Role.DIRECTOR)] == [
            "APPROVED", "NEEDS_REVISION", "REJECTED"]

    def test_applicant_from_rejected(self):
        assert [t.value for t in tr.allowed_targets(
            Carrier.APPLICATION, S.REJECTED, Role.APPLICANT)] == [
            "APPEAL_SUBMITTED", "EXPIRED", "RESUBMITTED", "WITHDRAWN"]

    def test_nothing_from_terminal_state(self):
        assert tr.allowed_targets(Carrier.APPLICATION, S.WITHDRAWN, Role.APPLICANT) == []
