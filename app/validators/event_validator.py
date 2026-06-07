"""
Validation layer.

Each event type has its own set of rules. A rule returns a ValidationResult row.
The validator runs all applicable rules and returns the full list.

Rules are structured so new ones can be added per event type without touching
the service layer — just add a function to the relevant rule set.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Event,
    EventType,
    Student,
    StudentInstitutionEnrolment,
    EnrolmentStatus,
    ValidationOutcome,
    ValidationResult,
)


def _pass(field: str, rule: str) -> ValidationResult:
    return ValidationResult(field_name=field, rule=rule, outcome=ValidationOutcome.PASS)


def _fail(field: str, rule: str, message: str) -> ValidationResult:
    return ValidationResult(field_name=field, rule=rule, outcome=ValidationOutcome.FAIL, message=message)


def _warn(field: str, rule: str, message: str) -> ValidationResult:
    return ValidationResult(field_name=field, rule=rule, outcome=ValidationOutcome.WARNING, message=message)


# ── RSA ID Luhn check ─────────────────────────────────────────────────────────

def _luhn_check(id_number: str) -> bool:
    """South African ID numbers satisfy the Luhn algorithm."""
    digits = [int(d) for d in id_number]
    odd_sum = sum(digits[-1::-2])
    even_digits = digits[-2::-2]
    even_sum = sum(sum(divmod(2 * d, 10)) for d in even_digits)
    return (odd_sum + even_sum) % 10 == 0


def validate_rsa_id(rsa_id: str) -> list[ValidationResult]:
    results = []
    if not rsa_id or not rsa_id.isdigit() or len(rsa_id) != 13:
        results.append(_fail("rsa_id_number", "format", "Must be exactly 13 digits"))
        return results
    results.append(_pass("rsa_id_number", "format"))

    if not _luhn_check(rsa_id):
        results.append(_fail("rsa_id_number", "luhn_check", "ID number fails Luhn checksum — likely a typo"))
    else:
        results.append(_pass("rsa_id_number", "luhn_check"))

    return results


# ── Registration rules ────────────────────────────────────────────────────────

async def validate_registration(event: Event, db: AsyncSession) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    p = event.payload

    # Required fields
    for field in ["institution_student_number", "academic_year", "qualification_name",
                  "nqf_level", "total_qualification_credits", "year_of_study",
                  "accommodation_type", "registration_date"]:
        if field not in p or p[field] is None:
            results.append(_fail(field, "required", f"Field '{field}' is required"))
        else:
            results.append(_pass(field, "required"))

    if len(results) > len([r for r in results if r.outcome == ValidationOutcome.PASS]):
        # Missing required fields — stop here, remaining checks would be meaningless
        return results

    # NQF level range
    nqf = p.get("nqf_level")
    if nqf is not None and not (5 <= int(nqf) <= 8):
        results.append(_fail("nqf_level", "range", "NQF level must be between 5 and 8 for university students"))
    elif nqf is not None:
        results.append(_pass("nqf_level", "range"))

    # Credits sanity
    credits = p.get("total_qualification_credits")
    if credits is not None and int(credits) < 120:
        results.append(_fail("total_qualification_credits", "minimum", "Total credits cannot be less than 120"))
    elif credits is not None:
        results.append(_pass("total_qualification_credits", "minimum"))

    # Duplicate active enrolment check — one active enrolment per student per academic year
    if event.student_id:
        result = await db.execute(
            select(StudentInstitutionEnrolment).where(
                StudentInstitutionEnrolment.student_id == event.student_id,
                StudentInstitutionEnrolment.academic_year == int(p.get("academic_year", 0)),
                StudentInstitutionEnrolment.status == EnrolmentStatus.active,
                StudentInstitutionEnrolment.institution_id != event.institution_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            results.append(_fail(
                "student_id",
                "duplicate_registration",
                f"Student already has an active registration at another institution for {p.get('academic_year')}",
            ))
        else:
            results.append(_pass("student_id", "duplicate_registration"))

    return results


# ── Results rules ─────────────────────────────────────────────────────────────

async def validate_results(event: Event, db: AsyncSession) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    p = event.payload

    for field in ["academic_year", "term", "credits_attempted", "credits_passed", "pass_rate"]:
        if field not in p or p[field] is None:
            results.append(_fail(field, "required", f"Field '{field}' is required"))
        else:
            results.append(_pass(field, "required"))

    # Pass rate consistency check
    attempted = p.get("credits_attempted")
    passed = p.get("credits_passed")
    if attempted and passed:
        if int(passed) > int(attempted):
            results.append(_fail("credits_passed", "consistency", "Credits passed cannot exceed credits attempted"))
        else:
            results.append(_pass("credits_passed", "consistency"))

        declared_rate = p.get("pass_rate")
        if declared_rate is not None and attempted > 0:
            computed_rate = round(int(passed) / int(attempted), 4)
            if abs(float(declared_rate) - computed_rate) > 0.01:
                results.append(_warn(
                    "pass_rate",
                    "consistency",
                    f"Declared pass rate {declared_rate} does not match computed rate {computed_rate}",
                ))
            else:
                results.append(_pass("pass_rate", "consistency"))

        # Flag students below 60% threshold — NSFAS uses this for continued funding
        if declared_rate is not None and float(declared_rate) < 0.60:
            results.append(_warn(
                "pass_rate",
                "nsfas_threshold",
                "Pass rate below 60% — student may be at risk of funding termination",
            ))

    return results


# ── Deregistration rules ──────────────────────────────────────────────────────

async def validate_deregistration(event: Event, db: AsyncSession) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    p = event.payload

    for field in ["reason", "effective_date"]:
        if field not in p or p[field] is None:
            results.append(_fail(field, "required", f"Field '{field}' is required"))
        else:
            results.append(_pass(field, "required"))

    valid_reasons = {
        "withdrawal", "graduation", "n_plus_exceeded",
        "qualification_change", "transfer_out", "academic_exclusion", "other"
    }
    reason = p.get("reason")
    if reason and reason not in valid_reasons:
        results.append(_fail("reason", "enum", f"Reason must be one of: {', '.join(sorted(valid_reasons))}"))
    elif reason:
        results.append(_pass("reason", "enum"))

    return results


# ── Dispatcher ────────────────────────────────────────────────────────────────

async def validate_event(event: Event, db: AsyncSession) -> list[ValidationResult]:
    """
    Entry point. Runs RSA ID validation (universal) then event-type-specific rules.
    Returns the full list of ValidationResult objects (not yet persisted).
    """
    results: list[ValidationResult] = []

    # RSA ID is universal for all inbound events
    # The RSA ID comes from the student record, not the payload
    if event.student_id:
        from sqlalchemy import select
        result = await db.execute(
            select(Student).where(Student.id == event.student_id)
        )
        student = result.scalar_one_or_none()
        if student:
            results.extend(validate_rsa_id(student.rsa_id_number))

    # Event-type-specific rules
    if event.event_type == EventType.STUDENT_REGISTRATION_SUBMITTED:
        results.extend(await validate_registration(event, db))

    elif event.event_type == EventType.STUDENT_RESULTS_SUBMITTED:
        results.extend(await validate_results(event, db))

    elif event.event_type == EventType.STUDENT_DEREGISTERED:
        results.extend(await validate_deregistration(event, db))

    # Outbound event types don't go through inbound validation.
    # They originate from NSFAS and are treated as authoritative.

    return results