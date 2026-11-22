"""Reusable server-side validators. Pure Python. BR ids are the specification's own."""
import re
from datetime import date
from decimal import Decimal

from .errors import ValidationFailed
from .ownership import validate_shares
from .states import AppealOutcome, FilingType, Recommendation, ReviewDecision

# BR-015 "under 50 MB". The unit and the exact-50 boundary are open (D-17, A-49): 50 MiB,
# strictly under. AFR-040 says "larger than 50 MB" is rejected, which differs at exactly 50.
MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
MIN_JUSTIFICATION_CHARS = 50  # BR-030

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_TEXT_FIELDS = ("title", "abstract", "detailed_description", "claims")  # BR-017, UC-001


# Column limits from the blueprint's entity specification. Rejecting longer values here keeps a
# database DataError from surfacing as a server error.
MAX_TITLE = 300
MAX_FULL_NAME = 200
MAX_EMAIL = 254
MAX_FILENAME = 255


def ensure_text(value, field, code="INVALID_TEXT"):
    """A value that must be text: not another type, and free of NUL characters, which
    PostgreSQL cannot store. Returns the value unchanged."""
    if not isinstance(value, str):
        raise ValidationFailed(code, f"{field} must be text.", {"field": field})
    if "\x00" in value:
        raise ValidationFailed(code, f"{field} contains an invalid character.",
                               {"field": field})
    return value


def _blank(value):
    return value is None or not str(value).strip()


def sanitize_filename(name):
    """A display-safe file name: no directory parts, no control characters, bounded length.

    The stored object key is opaque and never derived from this value (blueprint A-19).
    """
    ensure_text(name, "filename", "INVALID_FILENAME")
    base = name if re.search(r"<[^>]+>", name) else name.replace("\\", "/").split("/")[-1]
    cleaned = "".join(ch for ch in base if ch.isprintable() and ch not in "\x00").strip().lstrip(".")
    if not cleaned:
        raise ValidationFailed("INVALID_FILENAME", "File name is not valid.")
    return cleaned[:MAX_FILENAME]


def validate_pdf(filename, content_type, head):
    """BR-014: the document must be a PDF (extension, content type and file signature)."""
    problems = []
    if not isinstance(filename, str) or not filename.lower().endswith(".pdf"):
        problems.append("filename must end in .pdf")
    if (not isinstance(content_type, str)
            or content_type.lower().split(";")[0].strip() != "application/pdf"):
        problems.append("content type must be application/pdf")
    if not isinstance(head, bytes | bytearray) or not bytes(head).startswith(b"%PDF-"):
        problems.append("file content is not a PDF")
    if problems:
        raise ValidationFailed("INVALID_DOCUMENT_TYPE", "Only PDF documents are accepted.",
                               {"rule": "BR-PMS-014", "problems": problems})


def validate_size(size_bytes, max_bytes=MAX_DOCUMENT_BYTES):
    """BR-015: strictly under the limit."""
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
        raise ValidationFailed("INVALID_DOCUMENT_SIZE", "Document size is not valid.",
                               {"rule": "BR-PMS-015"})
    if size_bytes >= max_bytes:
        raise ValidationFailed("DOCUMENT_TOO_LARGE", "Document must be under 50 MB.",
                               {"rule": "BR-PMS-015", "size_bytes": size_bytes,
                                "max_bytes": max_bytes})


def validate_justification(text):
    """BR-030: at least 50 characters, counted on the stripped text (A-08)."""
    stripped = ensure_text(text if text is not None else "", "justification").strip()
    if len(stripped) < MIN_JUSTIFICATION_CHARS:
        raise ValidationFailed(
            "JUSTIFICATION_TOO_SHORT",
            f"Justification must be at least {MIN_JUSTIFICATION_CHARS} characters.",
            {"rule": "BR-PMS-030", "length": len(stripped)})
    return stripped


def validate_decision(value):
    """BR-029: exactly one of Approve, Reject, Needs Revision."""
    try:
        return ReviewDecision(value)
    except ValueError:
        raise ValidationFailed("INVALID_DECISION",
                               "Decision must be one of Approve, Reject, Needs Revision.",
                               {"rule": "BR-PMS-029"}) from None


def validate_appeal_outcome(value):
    """BR-095: exactly one of the three specified outcomes."""
    try:
        return AppealOutcome(value)
    except ValueError:
        raise ValidationFailed("INVALID_APPEAL_OUTCOME", "Unsupported appeal outcome.",
                               {"rule": "BR-PMS-095"}) from None


def validate_recommendation(value):
    """BR-046: exactly one of File Patent, Do Not File, Needs Amendment."""
    try:
        return Recommendation(value)
    except ValueError:
        raise ValidationFailed("INVALID_RECOMMENDATION", "Unsupported recommendation.",
                               {"rule": "BR-PMS-046"}) from None


def validate_grounds(text):
    """BR-094: appeal grounds are required."""
    if text is not None:
        ensure_text(text, "grounds")
    if _blank(text):
        raise ValidationFailed("GROUNDS_REQUIRED", "Appeal grounds are required.",
                               {"rule": "BR-PMS-094"})
    return text.strip()


def validate_reason(text):
    """BR-069: a withdrawal reason is required."""
    if text is not None:
        ensure_text(text, "reason")
    if _blank(text):
        raise ValidationFailed("REASON_REQUIRED", "A withdrawal reason is required.",
                               {"rule": "BR-PMS-069"})
    return text.strip()


def validate_inventor(full_name, email):
    """BR-073 (content unspecified; blueprint A-41, D-21): name present, email well formed."""
    problems = []
    for field, value in (("full_name", full_name), ("email", email)):
        if value is not None:
            ensure_text(value, field, "INVALID_INVENTOR")
    if _blank(full_name):
        problems.append("full_name is required")
    elif len(full_name.strip()) > MAX_FULL_NAME:
        problems.append(f"full_name is longer than {MAX_FULL_NAME} characters")
    if _blank(email) or not _EMAIL.match(email.strip()) or len(email.strip()) > MAX_EMAIL:
        problems.append("email is not valid")
    if problems:
        raise ValidationFailed("INVALID_INVENTOR", "Inventor information is not valid.",
                               {"rule": "BR-PMS-073", "problems": problems})
    return str(full_name).strip(), str(email).strip().lower()


def validate_inventor_set(inventors):
    """Each inventor valid, emails unique, shares valid (BR-073, BR-074)."""
    seen = set()
    for item in inventors:
        _, email = validate_inventor(item["full_name"], item["email"])
        if email in seen:
            raise ValidationFailed("DUPLICATE_INVENTOR", "An inventor is listed twice.",
                                   {"rule": "BR-PMS-073", "email": email})
        seen.add(email)
    validate_shares([i["ownership_percentage"] for i in inventors])


def validate_submission_complete(fields, inventors):
    """BR-017: every required item present. Lists all missing items at once.

    Required here: title, abstract, detailed description, claims, and inventor information
    (UC-001 step 1). Whether documents and domain are required is open (D-20); neither is.
    """
    for name in REQUIRED_TEXT_FIELDS:
        if fields.get(name) is not None:
            ensure_text(fields[name], name, "INVALID_FIELD")
    if len(fields.get("title") or "") > MAX_TITLE:
        raise ValidationFailed("FIELD_TOO_LONG", f"title is longer than {MAX_TITLE} characters.",
                               {"rule": "BR-PMS-017", "field": "title"})
    missing = [name for name in REQUIRED_TEXT_FIELDS if _blank(fields.get(name))]
    if not inventors:
        missing.append("inventors")
    if missing:
        raise ValidationFailed("SUBMISSION_INCOMPLETE", "Required information is missing.",
                               {"rule": "BR-PMS-017", "missing": missing})
    validate_inventor_set(inventors)


def validate_filing_details(filing_type, justification):
    """BR-056: international filings need a justification."""
    try:
        kind = FilingType(filing_type)
    except ValueError:
        raise ValidationFailed("INVALID_FILING_TYPE", "Filing type must be National or "
                               "International.", {"rule": "BR-PMS-056"}) from None
    if kind == FilingType.INTERNATIONAL and _blank(justification):
        raise ValidationFailed("INTERNATIONAL_JUSTIFICATION_REQUIRED",
                               "International filing requires a justification.",
                               {"rule": "BR-PMS-056"})


def validate_filing_identifiers(filing_id, filing_date, confirmation):
    """BR-142: Filed is recorded only with an id, a date and a confirmation reference."""
    missing = []
    if _blank(filing_id):
        missing.append("external_filing_id")
    if not isinstance(filing_date, date):
        missing.append("filing_date")
    if _blank(confirmation):
        missing.append("confirmation_reference")
    if missing:
        raise ValidationFailed("FILING_CONFIRMATION_MISSING",
                               "Filing id, date and confirmation are required.",
                               {"rule": "BR-PMS-142", "missing": missing})


def require_decimal(value, field):
    try:
        number = Decimal(str(value))
    except (ArithmeticError, ValueError):
        raise ValidationFailed("INVALID_AMOUNT", f"{field} is not a number.") from None
    if not number.is_finite():
        raise ValidationFailed("INVALID_AMOUNT", f"{field} is not a number.")
    return number
