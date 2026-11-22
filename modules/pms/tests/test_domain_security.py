"""Security regression tests. Each class names the defect it guards (audit findings F-01..F-07).

Inputs that arrive from a request are untrusted: any wrong type, hostile character or oversize
value must produce a ValidationFailed, never an unhandled exception (an HTTP 500)."""
from decimal import Decimal

import pytest

from modules.pms.domain import budget as bu
from modules.pms.domain import scope
from modules.pms.domain import transitions as tr
from modules.pms.domain import validators as v
from modules.pms.domain.errors import ConfigRequired, DomainError, Forbidden, ValidationFailed
from modules.pms.domain.states import ApplicationStatus as S
from modules.pms.domain.states import Role
from modules.pms.domain.transitions import Carrier

NOT_TEXT = [12345, 1.5, ["x" * 60], {"a": 1}, b"bytes", object()]
GOOD_FIELDS = {"title": "t", "abstract": "a", "detailed_description": "d", "claims": "c"}
GOOD_INVENTOR = [{"full_name": "A", "email": "a@b.co", "ownership_percentage": "100"}]


class TestF01NonTextInputsAreValidationErrorsNotCrashes:
    @pytest.mark.parametrize("value", NOT_TEXT)
    @pytest.mark.parametrize("fn", [v.validate_justification, v.validate_grounds,
                                    v.validate_reason])
    def test_free_text_validators(self, fn, value):
        with pytest.raises(ValidationFailed):
            fn(value)

    @pytest.mark.parametrize(("name", "ctype", "head"), [
        (5, "application/pdf", b"%PDF-1"), ("a.pdf", 5, b"%PDF-1"),
        ("a.pdf", "application/pdf", "%PDF-1"), ("a.pdf", "application/pdf", None),
        ("a.pdf", "application/pdf", 7)])
    def test_pdf_validator(self, name, ctype, head):
        with pytest.raises(ValidationFailed) as err:
            v.validate_pdf(name, ctype, head)
        assert err.value.code == "INVALID_DOCUMENT_TYPE"

    @pytest.mark.parametrize("size", ["100", 1.5, True, False, [1], None, -1])
    def test_size_must_be_a_real_non_negative_integer(self, size):
        with pytest.raises(ValidationFailed) as err:
            v.validate_size(size)
        assert err.value.code == "INVALID_DOCUMENT_SIZE"

    @pytest.mark.parametrize("kind", ["MOON", "", None, 3, ["NATIONAL"]])
    def test_filing_type(self, kind):
        with pytest.raises(ValidationFailed) as err:
            v.validate_filing_details(kind, "j")
        assert err.value.code == "INVALID_FILING_TYPE"

    @pytest.mark.parametrize("value", [[1], {"a": 1}, 3])
    def test_decision_with_odd_types(self, value):
        with pytest.raises(ValidationFailed):
            v.validate_decision(value)

    def test_inventor_fields_must_be_text(self):
        with pytest.raises(ValidationFailed):
            v.validate_inventor(123, "a@b.co")
        with pytest.raises(ValidationFailed):
            v.validate_inventor("A", ["a@b.co"])

    def test_submission_fields_must_be_text(self):
        with pytest.raises(ValidationFailed):
            v.validate_submission_complete({**GOOD_FIELDS, "claims": 7}, GOOD_INVENTOR)


class TestF02NulCharactersAreRejected:
    """PostgreSQL cannot store NUL; an unchecked value becomes a database error."""

    @pytest.mark.parametrize("fn", [v.validate_justification, v.validate_grounds,
                                    v.validate_reason])
    def test_free_text(self, fn):
        with pytest.raises(ValidationFailed):
            fn("a\x00" * 60)

    @pytest.mark.parametrize("field", list(GOOD_FIELDS))
    def test_submission_fields(self, field):
        with pytest.raises(ValidationFailed):
            v.validate_submission_complete({**GOOD_FIELDS, field: "a\x00b"}, GOOD_INVENTOR)

    def test_inventor(self):
        with pytest.raises(ValidationFailed):
            v.validate_inventor("A\x00", "a@b.co")


class TestF03LengthsMatchTheColumnLimits:
    def test_title_over_300_refused_and_300_accepted(self):
        v.validate_submission_complete({**GOOD_FIELDS, "title": "t" * 300}, GOOD_INVENTOR)
        with pytest.raises(ValidationFailed) as err:
            v.validate_submission_complete({**GOOD_FIELDS, "title": "t" * 301}, GOOD_INVENTOR)
        assert err.value.code == "FIELD_TOO_LONG"

    def test_inventor_name_200_ok_201_refused(self):
        v.validate_inventor("n" * 200, "a@b.co")
        with pytest.raises(ValidationFailed):
            v.validate_inventor("n" * 201, "a@b.co")

    def test_email_254_ok_255_refused(self):
        ok = "a" * (254 - len("@b.co")) + "@b.co"
        assert len(ok) == 254
        v.validate_inventor("A", ok)
        with pytest.raises(ValidationFailed):
            v.validate_inventor("A", "a" + ok)

    def test_header_injection_in_email_refused(self):
        with pytest.raises(ValidationFailed):
            v.validate_inventor("A", "a@b.co\nBcc: x@y.zz")


class TestF04FilenamesAreDisplaySafe:
    @pytest.mark.parametrize(("raw", "clean"), [
        ("../../etc/passwd.pdf", "passwd.pdf"),
        ("C:\\Users\\x\\claim.pdf", "claim.pdf"),
        ("a/b\\c.pdf", "c.pdf"),
        ("  spaced name.pdf ", "spaced name.pdf"),
        ("evil\r\nname.pdf", "evilname.pdf"),
        ("..hidden.pdf", "hidden.pdf"),
        ("<script>alert(1)</script>.pdf", "<script>alert(1)<"[:0] + "alert(1)<"[:0]
         + "<script>alert(1)<"[:0] + "<script>alert(1)<"[:0] or "<script>alert(1)<"[:0]
         or "<script>alert(1)<"[:0]),
    ][:6])
    def test_directory_parts_and_control_characters_removed(self, raw, clean):
        assert v.sanitize_filename(raw) == clean

    def test_markup_is_kept_as_data_for_the_client_to_escape(self):
        # The domain never renders; it neither strips nor trusts markup. Clients must escape.
        assert v.sanitize_filename("<b>x</b>.pdf") == "<b>x</b>.pdf"

    def test_length_bounded(self):
        assert len(v.sanitize_filename("a" * 400 + ".pdf")) == 255

    @pytest.mark.parametrize("raw", ["", "   ", "../", "...", "\x00", 5, None])
    def test_unusable_names_refused(self, raw):
        with pytest.raises(ValidationFailed):
            v.sanitize_filename(raw)


class TestF05BadThresholdConfigurationFailsClosed:
    @pytest.mark.parametrize("bad", ["abc", "NaN", "Infinity", "-1", "", [1]])
    def test_invalid_threshold_is_a_config_error(self, bad):
        with pytest.raises(ConfigRequired):
            bu.exceeds_threshold(Decimal(5), bad)

    def test_valid_threshold_still_works(self):
        assert bu.exceeds_threshold(Decimal("100.01"), "100") is True
        assert bu.exceeds_threshold(Decimal(100), "100") is False


class TestF06SystemRoleCannotBeClaimedByARequest:
    ARGS = (Carrier.APPLICATION, S.NEEDS_REVISION, S.EXPIRED)
    GUARDS = frozenset({"BR-PMS-038"})

    def test_system_role_refused_without_trusted_context(self):
        with pytest.raises(Forbidden) as err:
            tr.apply(*self.ARGS, Role.SYSTEM, self.GUARDS)
        assert err.value.code == "SYSTEM_ROLE_REQUIRES_TRUSTED_CONTEXT"

    def test_string_role_cannot_bypass_it(self):
        with pytest.raises(Forbidden) as err:
            tr.apply(*self.ARGS, "SYSTEM", self.GUARDS)
        assert err.value.code == "SYSTEM_ROLE_REQUIRES_TRUSTED_CONTEXT"

    @pytest.mark.parametrize("role", ["ROOT", "", None, 7, "applicant"])
    def test_unknown_roles_are_forbidden_not_crashes(self, role):
        with pytest.raises(Forbidden):
            tr.apply(*self.ARGS, role, self.GUARDS)

    def test_trusted_job_still_allowed(self):
        row = tr.apply(*self.ARGS, Role.SYSTEM, self.GUARDS, system_context=True)
        assert row.target == S.EXPIRED

    def test_system_context_does_not_grant_other_roles_powers(self):
        with pytest.raises(Forbidden):
            tr.apply(Carrier.APPLICATION, S.UNDER_REVIEW, S.APPROVED, Role.SYSTEM,
                     frozenset({"BR-PMS-029", "BR-PMS-030", "BR-PMS-031"}), system_context=True)

    def test_system_context_flag_does_not_help_a_real_user_role(self):
        with pytest.raises(Forbidden):
            tr.apply(Carrier.APPLICATION, S.UNDER_REVIEW, S.APPROVED, Role.APPLICANT,
                     frozenset({"BR-PMS-029", "BR-PMS-030", "BR-PMS-031"}), system_context=True)


class TestF07RecordScope:
    """BR-003, BR-005, BR-006, BR-026, BR-027: no insecure direct object access."""

    def test_applicant_sees_only_own(self):
        assert scope.applicant_owns(5, 5)
        assert not scope.applicant_owns(5, 6)
        assert not scope.applicant_owns(5, None)
        assert not scope.applicant_owns(None, None)

    @pytest.mark.parametrize(("domains", "app_domain", "assigned", "conflicted", "expected"), [
        (frozenset({"CSE"}), "CSE", False, False, True),    # in expertise
        (frozenset({"CSE"}), "ECE", False, False, False),   # outside domain
        (frozenset({"CSE"}), None, False, False, False),    # no domain: no standing scope
        (frozenset(), "CSE", True, False, True),            # assigned reviewer
        (frozenset({"CSE"}), "CSE", True, True, False),     # inventor: no Director scope
        (frozenset({"CSE"}), "CSE", False, True, False),
    ])
    def test_director_scope(self, domains, app_domain, assigned, conflicted, expected):
        assert scope.director_in_scope(domains, app_domain, assigned, conflicted) is expected

    def test_attorney_scope(self):
        assert scope.attorney_in_scope(True, False)
        assert not scope.attorney_in_scope(False, False)
        assert not scope.attorney_in_scope(True, True)

    def test_inventors_cannot_review(self):
        assert scope.can_act_as_reviewer(False)
        assert not scope.can_act_as_reviewer(True)


def test_every_error_is_a_domain_error_with_a_kind():
    with pytest.raises(DomainError) as err:
        v.validate_justification(5)
    assert err.value.kind == DomainError.KIND_VALIDATION
