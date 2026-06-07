"""
Pydantic schemas for all API request and response bodies.
Organised by domain: events, institutions, students, disbursements.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.models import (
    AccommodationType,
    AllowanceType,
    DisbursementStatus,
    EnrolmentStatus,
    EventDirection,
    EventStatus,
    EventType,
    InstitutionStatus,
    InstitutionType,
    PaymentChannel,
    ValidationOutcome,
)


# ── Shared ────────────────────────────────────────────────────────────────────

class PipeflowResponse(BaseModel):
    """Standard envelope for all API responses."""
    success: bool
    message: str | None = None
    data: Any = None


# ── Institutions ──────────────────────────────────────────────────────────────

class InstitutionCreate(BaseModel):
    institution_code: str = Field(..., max_length=20)
    name: str
    type: InstitutionType
    contact_email: str | None = None


class InstitutionResponse(BaseModel):
    id: uuid.UUID
    institution_code: str
    name: str
    type: InstitutionType
    status: InstitutionStatus
    contact_email: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InstitutionCreatedResponse(InstitutionResponse):
    """Returned once on creation — includes the raw API key. Never shown again."""
    api_key: str


# ── Students ──────────────────────────────────────────────────────────────────

class StudentCreate(BaseModel):
    rsa_id_number: str = Field(..., min_length=13, max_length=13)
    first_name: str
    last_name: str

    @field_validator("rsa_id_number")
    @classmethod
    def validate_rsa_id(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("RSA ID number must contain only digits")
        return v


class StudentResponse(BaseModel):
    id: uuid.UUID
    rsa_id_number: str
    first_name: str
    last_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Events ────────────────────────────────────────────────────────────────────

class EventSubmit(BaseModel):
    """Base schema for submitting any inbound event."""
    event_type: EventType
    student_rsa_id: str = Field(..., min_length=13, max_length=13)
    payload: dict[str, Any] = Field(..., description="Event-specific data. See payload contracts per event type.")

    @field_validator("student_rsa_id")
    @classmethod
    def validate_rsa_id(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("RSA ID number must contain only digits")
        return v


class EventStatusLogEntry(BaseModel):
    from_status: EventStatus | None
    to_status: EventStatus
    reason: str | None
    changed_by: str
    changed_at: datetime

    model_config = {"from_attributes": True}


class ValidationResultEntry(BaseModel):
    field_name: str
    rule: str
    outcome: ValidationOutcome
    message: str | None

    model_config = {"from_attributes": True}


class EventResponse(BaseModel):
    id: uuid.UUID
    event_type: EventType
    direction: EventDirection
    status: EventStatus
    institution_id: uuid.UUID
    student_id: uuid.UUID | None
    nsfas_reference: str | None
    parent_event_id: uuid.UUID | None
    submitted_at: datetime
    processed_at: datetime | None
    status_log: list[EventStatusLogEntry] = []
    validation_results: list[ValidationResultEntry] = []

    model_config = {"from_attributes": True}


# ── Payload contracts (typed schemas per event type) ──────────────────────────
# These are used by the validation layer to check payload fields.

class RegistrationPayload(BaseModel):
    institution_student_number: str
    academic_year: int = Field(..., ge=2020, le=2040)
    qualification_name: str
    nqf_level: int = Field(..., ge=5, le=8)
    total_qualification_credits: int = Field(..., ge=120)
    year_of_study: int = Field(..., ge=1, le=10)
    accommodation_type: AccommodationType
    has_disability: bool = False
    registration_date: datetime
    credits_registered_this_term: int = Field(..., ge=0)


class ResultsPayload(BaseModel):
    academic_year: int
    term: str  # e.g. "S1", "S2", "Y"
    credits_attempted: int
    credits_passed: int
    pass_rate: float = Field(..., ge=0.0, le=1.0)
    graduated: bool = False
    modules_registered: list[str] = []
    modules_passed: list[str] = []


class DeregistrationPayload(BaseModel):
    reason: str  # DeregistrationReason enum value
    effective_date: datetime
    notes: str | None = None


# ── Disbursements ─────────────────────────────────────────────────────────────

class DisbursementResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    institution_id: uuid.UUID
    allowance_type: AllowanceType
    amount_rands: float
    academic_year: int
    payment_period: str
    payment_channel: PaymentChannel
    status: DisbursementStatus
    failure_reason: str | None
    scheduled_at: datetime
    processed_at: datetime | None

    model_config = {"from_attributes": True}