"""COI (BR-025..027, 044), routing (BR-022..024), attorney (BR-040..045, 127),
budget (BR-048..053), documents (BR-084..087, 130)."""
from decimal import Decimal

import pytest

from modules.pms.domain import attorney_rules as ar
from modules.pms.domain import budget as bu
from modules.pms.domain import document_policy as dp
from modules.pms.domain import routing as rt
from modules.pms.domain.coi import ListedInventor, is_conflicted
from modules.pms.domain.errors import (
    ConfigRequired,
    Conflict,
    Forbidden,
    InvalidState,
    Unprocessable,
    ValidationFailed,
)
from modules.pms.domain.states import (
    ApplicationStatus as S,
)
from modules.pms.domain.states import (
    AttorneyState,
    BudgetOutcome,
    Role,
    display_state,
)


class TestConflictOfInterest:
    def test_matched_by_user_id(self):
        assert is_conflicted(7, None, [ListedInventor(7, None)])

    def test_matched_by_directory_email_when_inventor_has_no_user_id(self):
        assert is_conflicted(7, "Dir@Inst.Edu", [ListedInventor(None, "dir@inst.edu")])

    def test_email_not_used_when_inventor_has_a_different_user_id(self):
        assert not is_conflicted(7, "dir@inst.edu", [ListedInventor(9, "dir@inst.edu")])

    def test_not_listed_is_not_conflicted(self):
        assert not is_conflicted(7, "x@y.zz", [ListedInventor(8, "a@b.cc")])

    def test_none_user_without_email_never_matches_empty_inventor(self):
        assert not is_conflicted(None, None, [ListedInventor(None, None)])


class TestDirectorRouting:
    A = rt.DirectorCandidate(1, frozenset({"CSE"}), 3)
    B = rt.DirectorCandidate(2, frozenset({"CSE", "ECE"}), 1)
    C = rt.DirectorCandidate(3, frozenset({"ECE"}), 0)
    D = rt.DirectorCandidate(4, frozenset({"CSE"}), 0, conflicted=True)

    def test_conflicted_and_mismatched_excluded_lowest_load_first(self):
        assert [c.user_id for c in rt.rank_directors([self.A, self.B, self.C, self.D], "CSE")] \
            == [2, 1]

    def test_no_domain_means_any_non_conflicted_director(self):
        assert [c.user_id for c in rt.rank_directors([self.A, self.C, self.D], None)] == [3, 1]

    def test_ties_break_on_user_id(self):
        x = rt.DirectorCandidate(9, frozenset({"CSE"}), 1)
        y = rt.DirectorCandidate(5, frozenset({"CSE"}), 1)
        assert [c.user_id for c in rt.rank_directors([x, y], "CSE")] == [5, 9]

    def test_none_eligible_raises_unprocessable(self):
        with pytest.raises(Unprocessable) as err:
            rt.require_director([self.D, self.C], "CSE")
        assert err.value.code == "NO_ELIGIBLE_DIRECTOR"

    def test_automatic_and_manual_use_the_same_ranking(self):
        pool = [self.A, self.B, self.C]
        assert rt.rank_directors(pool, "ECE") == rt.require_director(pool, "ECE")


class TestAttorneyRouting:
    def test_panel_or_exception_required(self):
        panel = rt.AttorneyCandidate(1, in_panel=True)
        exc = rt.AttorneyCandidate(2, has_exception=True)
        out = rt.AttorneyCandidate(3)
        assert [c.user_id for c in rt.rank_attorneys([out, exc, panel], None)] == [1, 2]

    def test_conflicted_excluded(self):
        bad = rt.AttorneyCandidate(1, in_panel=True, conflicted=True)
        assert rt.rank_attorneys([bad], None) == []

    def test_preference_applies_only_when_on_panel(self):
        pref_panel = rt.AttorneyCandidate(5, in_panel=True, preferred=True, active_load=9)
        pref_exc = rt.AttorneyCandidate(6, has_exception=True, preferred=True, active_load=3)
        light = rt.AttorneyCandidate(7, in_panel=True, active_load=0)
        # The preferred panel member leads; the preferred non-panel Attorney gets no boost.
        assert [c.user_id for c in rt.rank_attorneys([light, pref_exc, pref_panel], None)] \
            == [5, 7, 6]

    def test_expertise_match_before_workload(self):
        a = rt.AttorneyCandidate(1, frozenset({"CSE"}), 5, in_panel=True)
        b = rt.AttorneyCandidate(2, frozenset(), 0, in_panel=True)
        assert [c.user_id for c in rt.rank_attorneys([b, a], "CSE")] == [1, 2]


class TestAttorneyGuards:
    def test_only_pcc_admin_assigns(self):  # BR-040
        ar.require_pcc_admin(Role.PCC_ADMIN)
        for role in (Role.DIRECTOR, Role.APPLICANT, Role.ATTORNEY):
            with pytest.raises(Forbidden):
                ar.require_pcc_admin(role)

    @pytest.mark.parametrize("status", [S.SUBMITTED, S.UNDER_REVIEW, S.NEEDS_REVISION,
                                        S.REJECTED, S.FILED])
    def test_only_approved_applications(self, status):  # BR-127
        with pytest.raises(InvalidState) as err:
            ar.require_approved(status)
        assert err.value.code == "NOT_APPROVED"

    def test_approved_passes(self):
        ar.require_approved(S.APPROVED)

    def test_panel_or_exception(self):  # BR-041
        ar.require_panel_or_exception(True, False)
        ar.require_panel_or_exception(False, True)
        with pytest.raises(Conflict) as err:
            ar.require_panel_or_exception(False, False)
        assert err.value.code == "NOT_IN_PANEL"

    def test_open_assignment_blocks_a_second_offer(self):
        ar.require_no_open_assignment(AttorneyState.NONE)
        ar.require_no_open_assignment(AttorneyState.DECLINED)
        for state in (AttorneyState.OFFERED, AttorneyState.ASSIGNED):
            with pytest.raises(Conflict):
                ar.require_no_open_assignment(state)


class TestBudget:
    def test_components_required_and_not_negative(self):  # BR-048..050
        assert bu.validate_components("10", "20.50", 5) == (
            Decimal("10"), Decimal("20.50"), Decimal("5"))
        with pytest.raises(ValidationFailed) as err:
            bu.validate_components(None, "", "1")
        assert err.value.details["missing"] == ["filing_fees", "attorney_fees"]
        with pytest.raises(ValidationFailed) as err2:
            bu.validate_components("-1", "1", "1")
        assert err2.value.code == "NEGATIVE_AMOUNT"

    def test_non_numeric_amount_refused(self):
        with pytest.raises(ValidationFailed):
            bu.validate_components("abc", "1", "1")
        with pytest.raises(ValidationFailed):
            bu.validate_components("NaN", "1", "1")

    def test_total_equal_to_threshold_is_within_it(self):  # A-48
        assert bu.decide(Decimal("100"), "100", "APPROVED") == BudgetOutcome.APPROVED

    def test_one_paisa_over_threshold_escalates_and_ignores_requested_outcome(self):
        assert bu.decide(Decimal("100.01"), "100", "REJECTED") == BudgetOutcome.ESCALATED

    def test_unset_threshold_refuses_the_decision(self):
        with pytest.raises(ConfigRequired):
            bu.decide(Decimal("1"), None, "APPROVED")

    def test_within_threshold_reject_is_recorded(self):
        assert bu.decide(Decimal("5"), "100", "REJECTED") == BudgetOutcome.REJECTED

    def test_invalid_outcome_refused_within_threshold(self):
        with pytest.raises(ValidationFailed):
            bu.decide(Decimal("5"), "100", "ESCALATED")

    @pytest.mark.parametrize("status", [S.SUBMITTED, S.UNDER_REVIEW, S.FILED, S.REJECTED])
    def test_budget_needs_literal_approved_status(self, status):  # BR-052
        with pytest.raises(InvalidState):
            bu.require_approved_status(status)

    def test_approved_status_passes_even_with_attorney_track_active(self):
        bu.require_approved_status(S.APPROVED)

    def test_availability_only_blocks_when_data_says_unavailable(self):  # BR-053
        bu.check_availability(None)
        bu.check_availability(True)
        with pytest.raises(InvalidState) as err:
            bu.check_availability(False)
        assert err.value.code == "BUDGET_NOT_AVAILABLE"

    def test_total(self):
        assert bu.total_cost(Decimal("1"), Decimal("2"), Decimal("3")) == Decimal("6")


class TestDocumentPolicy:
    def test_applicant_edits_documents_only_in_needs_revision(self):  # BR-087
        for status in S:
            expected = status == S.NEEDS_REVISION
            assert dp.can_edit_documents(Role.APPLICANT, True, status) is expected

    def test_non_owner_applicant_never_edits(self):
        assert not dp.can_edit_documents(Role.APPLICANT, False, S.NEEDS_REVISION)

    def test_other_roles_never_edit_as_applicant(self):
        for role in (Role.DIRECTOR, Role.PCC_ADMIN, Role.ATTORNEY):
            assert not dp.can_edit_documents(role, True, S.NEEDS_REVISION)

    def test_applicant_upload_in_draft_and_needs_revision_only(self):
        ok = {S.DRAFT, S.NEEDS_REVISION}
        for status in S:
            assert dp.can_upload(Role.APPLICANT, True, False, status) is (status in ok)

    def test_directors_and_admins_do_not_upload(self):
        for role in (Role.DIRECTOR, Role.PCC_ADMIN, Role.SYSTEM):
            assert not dp.can_upload(role, False, True, S.APPROVED)

    def test_attorney_uploads_after_acceptance_through_filing(self):
        assert dp.can_upload(Role.ATTORNEY, False, True, S.APPROVED, AttorneyState.ASSIGNED)
        assert dp.can_upload(Role.ATTORNEY, False, True, S.FILED)
        assert not dp.can_upload(Role.ATTORNEY, False, True, S.APPROVED, AttorneyState.OFFERED)
        assert not dp.can_upload(Role.ATTORNEY, False, False, S.FILED)

    def test_reading_current_version(self):
        assert dp.can_read(Role.APPLICANT, True, False, S.SUBMITTED, "CONFIDENTIAL")
        assert not dp.can_read(Role.APPLICANT, False, False, S.SUBMITTED, "CONFIDENTIAL")
        assert dp.can_read(Role.DIRECTOR, False, True, S.UNDER_REVIEW, "CONFIDENTIAL")
        assert not dp.can_read(Role.DIRECTOR, False, False, S.UNDER_REVIEW, "CONFIDENTIAL")

    def test_previous_versions_hidden_from_applicant_except_in_revision(self):  # BR-084
        assert not dp.can_read(Role.APPLICANT, True, False, S.SUBMITTED, "CONFIDENTIAL", False)
        assert dp.can_read(Role.APPLICANT, True, False, S.NEEDS_REVISION, "CONFIDENTIAL", False)

    def test_restricted_hidden_from_pcc_admin(self):  # BR-086, D-13
        assert dp.can_read(Role.PCC_ADMIN, False, False, S.SUBMITTED, "CONFIDENTIAL")
        assert not dp.can_read(Role.PCC_ADMIN, False, False, S.SUBMITTED, "RESTRICTED")

    def test_system_role_reads_nothing(self):
        assert not dp.can_read(Role.SYSTEM, False, False, S.SUBMITTED, "CONFIDENTIAL")


class TestDisplayState:
    def test_attorney_track_names_on_approved(self):
        assert display_state(S.APPROVED) == "Approved"
        assert display_state(S.APPROVED, AttorneyState.OFFERED) == "Assignment Offered"
        assert display_state(S.APPROVED, AttorneyState.ASSIGNED) == "Attorney Assigned"
        assert display_state(S.APPROVED, AttorneyState.DECLINED) == "Pending Review"

    def test_track_ignored_when_not_approved(self):
        assert display_state(S.FILED, AttorneyState.ASSIGNED) == "Filed"
