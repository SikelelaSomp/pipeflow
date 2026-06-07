from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_institution, require_nsfas, require_university
from app.db.session import get_db
from app.models.models import EventType, Institution
from app.schemas.schemas import EventResponse, EventSubmit, PipeflowResponse
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["Events"])


@router.post("", response_model=PipeflowResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_event(
    submission: EventSubmit,
    institution: Institution = Depends(require_university),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit an inbound event from a university to NSFAS via PipeFlow.

    Accepted event types:
    - STUDENT_REGISTRATION_SUBMITTED
    - STUDENT_RESULTS_SUBMITTED
    - STUDENT_DEREGISTERED

    The event is validated synchronously. A VALID event is immediately marked
    FORWARDED. An INVALID event is returned with the full list of failures.
    """
    inbound_types = {
        EventType.STUDENT_REGISTRATION_SUBMITTED,
        EventType.STUDENT_RESULTS_SUBMITTED,
        EventType.STUDENT_DEREGISTERED,
    }
    if submission.event_type not in inbound_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Event type {submission.event_type} cannot be submitted by an institution. "
                   f"Only NSFAS can originate outbound events.",
        )

    service = EventService(db)
    event = await service.submit_inbound_event(submission, institution)

    if event.status.value == "INVALID":
        failures = [
            {"field": vr.field_name, "rule": vr.rule, "message": vr.message}
            for vr in event.validation_results
            if vr.outcome.value == "FAIL"
        ]
        return PipeflowResponse(
            success=False,
            message="Event failed validation and was not forwarded",
            data={"event_id": str(event.id), "failures": failures},
        )

    return PipeflowResponse(
        success=True,
        message="Event received, validated, and forwarded to NSFAS",
        data={"event_id": str(event.id), "status": event.status.value},
    )


@router.get("/{event_id}", response_model=PipeflowResponse)
async def get_event(
    event_id: UUID,
    institution: Institution = Depends(get_current_institution),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve a specific event by ID.
    Institutions can only retrieve their own events.
    """
    service = EventService(db)
    event = await service.get_event(event_id)

    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    # Institutions can only see their own events
    from app.models.models import InstitutionType
    if institution.type != InstitutionType.nsfas and event.institution_id != institution.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return PipeflowResponse(
        success=True,
        data=EventResponse.model_validate(event),
    )


@router.get("", response_model=PipeflowResponse)
async def list_events(
    limit: int = 50,
    offset: int = 0,
    institution: Institution = Depends(get_current_institution),
    db: AsyncSession = Depends(get_db),
):
    """
    List events for the calling institution.
    NSFAS can see all events; universities see only their own.
    """
    from app.models.models import InstitutionType
    service = EventService(db)

    if institution.type == InstitutionType.nsfas:
        # NSFAS: list all events across all institutions
        from sqlalchemy import select
        from app.models.models import Event
        from sqlalchemy.orm import selectinload
        result = await db.execute(
            select(Event)
            .options(selectinload(Event.status_log), selectinload(Event.validation_results))
            .order_by(Event.submitted_at.desc())
            .limit(limit)
            .offset(offset)
        )
        events = list(result.scalars().all())
    else:
        events = await service.list_events_for_institution(institution.id, limit, offset)

    return PipeflowResponse(
        success=True,
        data=[EventResponse.model_validate(e) for e in events],
    )


@router.post("/outbound", response_model=PipeflowResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_outbound_event(
    event_type: EventType,
    institution_id: UUID,
    student_rsa_id: str | None = None,
    payload: dict = {},
    parent_event_id: UUID | None = None,
    nsfas_reference: str | None = None,
    _nsfas: Institution = Depends(require_nsfas),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit an outbound event originating from NSFAS, to be routed to an institution.
    Restricted to NSFAS API key only.

    Accepted event types:
    - FUNDING_DECISION_ISSUED
    - DISBURSEMENT_SCHEDULED
    - DISBURSEMENT_STATUS_UPDATED
    - FUNDING_SUSPENDED
    """
    outbound_types = {
        EventType.FUNDING_DECISION_ISSUED,
        EventType.DISBURSEMENT_SCHEDULED,
        EventType.DISBURSEMENT_STATUS_UPDATED,
        EventType.FUNDING_SUSPENDED,
    }
    if event_type not in outbound_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Event type {event_type} is not an outbound event type",
        )

    # Resolve student if RSA ID provided
    student_id = None
    if student_rsa_id:
        from sqlalchemy import select
        from app.models.models import Student
        result = await db.execute(select(Student).where(Student.rsa_id_number == student_rsa_id))
        student = result.scalar_one_or_none()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No student found with RSA ID {student_rsa_id}",
            )
        student_id = student.id

    service = EventService(db)
    event = await service.submit_outbound_event(
        event_type=event_type,
        institution_id=institution_id,
        student_id=student_id,
        payload=payload,
        parent_event_id=parent_event_id,
        nsfas_reference=nsfas_reference,
    )

    return PipeflowResponse(
        success=True,
        message="Outbound event recorded and routed to institution",
        data={"event_id": str(event.id), "status": event.status.value},
    )