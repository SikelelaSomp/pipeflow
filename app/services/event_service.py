"""
EventService: the heart of PipeFlow.

Responsibilities:
  1. Receive an inbound event submission from an institution
  2. Look up or create the student record by RSA ID
  3. Persist the event with status RECEIVED
  4. Write the initial status log entry
  5. Trigger validation
  6. Transition status to VALID or INVALID
  7. If valid, mark FORWARDED (actual NSFAS forwarding is a future integration layer)

Outbound events (NSFAS → university) follow the same pattern in reverse.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import (
    Event,
    EventDirection,
    EventStatus,
    EventStatusLog,
    EventType,
    Institution,
    Student,
    ValidationResult,
)
from app.schemas.schemas import EventSubmit
from app.validators.event_validator import validate_event


class EventService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_inbound_event(
        self,
        submission: EventSubmit,
        institution: Institution,
    ) -> Event:
        """
        Full pipeline for an inbound event from a university.
        Returns the event record with status_log and validation_results loaded.
        """

        # 1. Resolve student by RSA ID
        student = await self._get_or_create_student(submission.student_rsa_id)

        # 2. Persist event at RECEIVED
        event = Event(
            event_type=submission.event_type,
            direction=EventDirection.INBOUND,
            status=EventStatus.RECEIVED,
            institution_id=institution.id,
            student_id=student.id,
            payload=submission.payload,
        )
        self.db.add(event)
        await self.db.flush()  # get event.id without committing

        # 3. Write initial status log entry
        await self._log_transition(
            event=event,
            from_status=None,
            to_status=EventStatus.RECEIVED,
            changed_by=institution.institution_code,
        )

        # 4. Validate
        await self._transition(event, EventStatus.VALIDATING, changed_by="system")
        validation_results = await validate_event(event, self.db)

        for vr in validation_results:
            vr.event_id = event.id
            self.db.add(vr)

        # 5. Determine outcome
        has_failures = any(
            vr.outcome.value == "FAIL" for vr in validation_results
        )

        if has_failures:
            await self._transition(
                event,
                EventStatus.INVALID,
                changed_by="system",
                reason="One or more validation rules failed",
            )
        else:
            await self._transition(event, EventStatus.VALID, changed_by="system")
            # Mark as FORWARDED immediately — actual forwarding to NSFAS portal
            # will be handled by the integration layer in a future phase.
            await self._transition(
                event,
                EventStatus.FORWARDED,
                changed_by="system",
                reason="Queued for NSFAS forwarding",
            )
            event.processed_at = datetime.now(timezone.utc)

        await self.db.flush()

        # 6. Reload with relationships for response
        return await self._load_event(event.id)

    async def submit_outbound_event(
        self,
        event_type: EventType,
        institution_id: uuid.UUID,
        student_id: uuid.UUID | None,
        payload: dict,
        parent_event_id: uuid.UUID | None,
        nsfas_reference: str | None,
    ) -> Event:
        """
        Record an outbound event originating from NSFAS.
        These arrive via the NSFAS portal integration layer and are routed to the
        relevant institution.
        """
        event = Event(
            event_type=event_type,
            direction=EventDirection.OUTBOUND,
            status=EventStatus.RECEIVED,
            institution_id=institution_id,
            student_id=student_id,
            payload=payload,
            parent_event_id=parent_event_id,
            nsfas_reference=nsfas_reference,
        )
        self.db.add(event)
        await self.db.flush()

        await self._log_transition(
            event=event,
            from_status=None,
            to_status=EventStatus.RECEIVED,
            changed_by="nsfas",
        )

        # Outbound events from NSFAS skip internal validation (NSFAS is the authority).
        # Route directly to the institution.
        await self._transition(event, EventStatus.FORWARDED, changed_by="system")
        event.processed_at = datetime.now(timezone.utc)

        await self.db.flush()
        return await self._load_event(event.id)

    async def get_event(self, event_id: uuid.UUID) -> Event | None:
        return await self._load_event(event_id)

    async def list_events_for_institution(
        self,
        institution_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Event]:
        result = await self.db.execute(
            select(Event)
            .where(Event.institution_id == institution_id)
            .options(
                selectinload(Event.status_log),
                selectinload(Event.validation_results),
            )
            .order_by(Event.submitted_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _get_or_create_student(self, rsa_id_number: str) -> Student:
        result = await self.db.execute(
            select(Student).where(Student.rsa_id_number == rsa_id_number)
        )
        student = result.scalar_one_or_none()

        if not student:
            # Minimal record — name fields will be enriched from payload or DHA later
            student = Student(
                rsa_id_number=rsa_id_number,
                first_name="",
                last_name="",
            )
            self.db.add(student)
            await self.db.flush()

        return student

    async def _transition(
        self,
        event: Event,
        to_status: EventStatus,
        changed_by: str,
        reason: str | None = None,
    ) -> None:
        from_status = event.status
        event.status = to_status
        await self._log_transition(event, from_status, to_status, changed_by, reason)

    async def _log_transition(
        self,
        event: Event,
        from_status: EventStatus | None,
        to_status: EventStatus,
        changed_by: str,
        reason: str | None = None,
    ) -> None:
        log_entry = EventStatusLog(
            event_id=event.id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            changed_by=changed_by,
        )
        self.db.add(log_entry)

    async def _load_event(self, event_id: uuid.UUID) -> Event | None:
        result = await self.db.execute(
            select(Event)
            .where(Event.id == event_id)
            .options(
                selectinload(Event.status_log),
                selectinload(Event.validation_results),
            )
        )
        return result.scalar_one_or_none()