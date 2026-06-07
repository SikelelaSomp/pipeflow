import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

# ── Enums (mirroring schema.sql) ─────────────────────────────────────────────

import enum


class InstitutionType(str, enum.Enum):
    university = "university"
    tvet_college = "tvet_college"
    nsfas = "nsfas"


class InstitutionStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    inactive = "inactive"


class EventType(str, enum.Enum):
    STUDENT_REGISTRATION_SUBMITTED = "STUDENT_REGISTRATION_SUBMITTED"
    STUDENT_RESULTS_SUBMITTED = "STUDENT_RESULTS_SUBMITTED"
    STUDENT_DEREGISTERED = "STUDENT_DEREGISTERED"
    FUNDING_DECISION_ISSUED = "FUNDING_DECISION_ISSUED"
    DISBURSEMENT_SCHEDULED = "DISBURSEMENT_SCHEDULED"
    DISBURSEMENT_STATUS_UPDATED = "DISBURSEMENT_STATUS_UPDATED"
    FUNDING_SUSPENDED = "FUNDING_SUSPENDED"


class EventDirection(str, enum.Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class EventStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    VALID = "VALID"
    INVALID = "INVALID"
    FORWARDED = "FORWARDED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ValidationOutcome(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class EnrolmentStatus(str, enum.Enum):
    active = "active"
    deregistered = "deregistered"
    transferred_out = "transferred_out"
    graduated = "graduated"
    suspended = "suspended"


class AllowanceType(str, enum.Enum):
    tuition = "tuition"
    accommodation = "accommodation"
    living = "living"
    transport = "transport"
    learning_material = "learning_material"
    personal_care = "personal_care"
    disability_assistive = "disability_assistive"
    disability_human_support = "disability_human_support"


class PaymentChannel(str, enum.Enum):
    direct_to_student = "direct_to_student"
    direct_to_institution = "direct_to_institution"
    direct_to_accommodation_provider = "direct_to_accommodation_provider"


class DisbursementStatus(str, enum.Enum):
    scheduled = "scheduled"
    processed = "processed"
    failed = "failed"
    held = "held"
    reversed = "reversed"


class AccommodationType(str, enum.Enum):
    institution_catered = "institution_catered"
    institution_self_catering = "institution_self_catering"
    private_accredited = "private_accredited"
    home_commuter = "home_commuter"


class DeregistrationReason(str, enum.Enum):
    withdrawal = "withdrawal"
    graduation = "graduation"
    n_plus_exceeded = "n_plus_exceeded"
    qualification_change = "qualification_change"
    transfer_out = "transfer_out"
    academic_exclusion = "academic_exclusion"
    other = "other"


# ── Models ────────────────────────────────────────────────────────────────────

class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[InstitutionType] = mapped_column(Enum(InstitutionType, name="institution_type"), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[InstitutionStatus] = mapped_column(
        Enum(InstitutionStatus, name="institution_status"),
        nullable=False,
        default=InstitutionStatus.active,
    )
    contact_email: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    events: Mapped[list["Event"]] = relationship("Event", back_populates="institution")
    enrolments: Mapped[list["StudentInstitutionEnrolment"]] = relationship("StudentInstitutionEnrolment", back_populates="institution")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rsa_id_number: Mapped[str] = mapped_column(String(13), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    events: Mapped[list["Event"]] = relationship("Event", back_populates="student")
    enrolments: Mapped[list["StudentInstitutionEnrolment"]] = relationship("StudentInstitutionEnrolment", back_populates="student")
    disbursements: Mapped[list["Disbursement"]] = relationship("Disbursement", back_populates="student")


class StudentInstitutionEnrolment(Base):
    __tablename__ = "student_institution_enrolments"
    __table_args__ = (
        UniqueConstraint("institution_id", "institution_student_number", "academic_year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    institution_student_number: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EnrolmentStatus] = mapped_column(
        Enum(EnrolmentStatus, name="enrolment_status"),
        nullable=False,
        default=EnrolmentStatus.active,
    )
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False)
    qualification_name: Mapped[str] = mapped_column(Text, nullable=False)
    nqf_level: Mapped[int | None] = mapped_column(Integer)
    total_qualification_credits: Mapped[int | None] = mapped_column(Integer)
    year_of_study: Mapped[int] = mapped_column(Integer, nullable=False)
    accommodation_type: Mapped[AccommodationType | None] = mapped_column(Enum(AccommodationType, name="accommodation_type"))
    has_disability: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    student: Mapped["Student"] = relationship("Student", back_populates="enrolments")
    institution: Mapped["Institution"] = relationship("Institution", back_populates="enrolments")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType, name="event_type"), nullable=False)
    direction: Mapped[EventDirection] = mapped_column(Enum(EventDirection, name="event_direction"), nullable=False)
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status"),
        nullable=False,
        default=EventStatus.RECEIVED,
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    student_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id"))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    nsfas_reference: Mapped[str | None] = mapped_column(Text)
    parent_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    institution: Mapped["Institution"] = relationship("Institution", back_populates="events")
    student: Mapped["Student | None"] = relationship("Student", back_populates="events")
    status_log: Mapped[list["EventStatusLog"]] = relationship("EventStatusLog", back_populates="event", order_by="EventStatusLog.changed_at")
    validation_results: Mapped[list["ValidationResult"]] = relationship("ValidationResult", back_populates="event")
    disbursement: Mapped["Disbursement | None"] = relationship("Disbursement", back_populates="event", uselist=False)
    parent_event: Mapped["Event | None"] = relationship("Event", remote_side="Event.id")


class EventStatusLog(Base):
    __tablename__ = "event_status_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    from_status: Mapped[EventStatus | None] = mapped_column(Enum(EventStatus, name="event_status"))
    to_status: Mapped[EventStatus] = mapped_column(Enum(EventStatus, name="event_status"), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped["Event"] = relationship("Event", back_populates="status_log")


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    rule: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[ValidationOutcome] = mapped_column(Enum(ValidationOutcome, name="validation_outcome"), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped["Event"] = relationship("Event", back_populates="validation_results")


class Disbursement(Base):
    __tablename__ = "disbursements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    allowance_type: Mapped[AllowanceType] = mapped_column(Enum(AllowanceType, name="allowance_type"), nullable=False)
    amount_rands: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_period: Mapped[str] = mapped_column(Text, nullable=False)
    payment_channel: Mapped[PaymentChannel] = mapped_column(Enum(PaymentChannel, name="payment_channel"), nullable=False)
    status: Mapped[DisbursementStatus] = mapped_column(
        Enum(DisbursementStatus, name="disbursement_status"),
        nullable=False,
        default=DisbursementStatus.scheduled,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    event: Mapped["Event"] = relationship("Event", back_populates="disbursement")
    student: Mapped["Student"] = relationship("Student", back_populates="disbursements")
