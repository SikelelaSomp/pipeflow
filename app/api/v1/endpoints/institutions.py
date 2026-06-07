from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_nsfas
from app.core.security import generate_api_key, hash_api_key
from app.db.session import get_db
from app.models.models import Institution
from app.schemas.schemas import InstitutionCreate, InstitutionCreatedResponse, InstitutionResponse, PipeflowResponse

router = APIRouter(prefix="/institutions", tags=["Institutions"])


@router.post("", response_model=PipeflowResponse, status_code=status.HTTP_201_CREATED)
async def create_institution(
    data: InstitutionCreate,
    _nsfas=Depends(require_nsfas),
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new institution (university or TVET college) in PipeFlow.
    Restricted to NSFAS admin.
    Returns the raw API key once — store it securely. It cannot be retrieved again.
    """
    existing = await db.execute(
        select(Institution).where(Institution.institution_code == data.institution_code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Institution with code '{data.institution_code}' already exists",
        )

    raw_key = generate_api_key()
    institution = Institution(
        institution_code=data.institution_code,
        name=data.name,
        type=data.type,
        api_key_hash=hash_api_key(raw_key),
        contact_email=data.contact_email,
    )
    db.add(institution)
    await db.flush()

    return PipeflowResponse(
        success=True,
        message="Institution created. Store the API key — it will not be shown again.",
        data=InstitutionCreatedResponse(
            **InstitutionResponse.model_validate(institution).model_dump(),
            api_key=raw_key,
        ),
    )


@router.get("", response_model=PipeflowResponse)
async def list_institutions(
    _nsfas=Depends(require_nsfas),
    db: AsyncSession = Depends(get_db),
):
    """List all registered institutions. NSFAS only."""
    result = await db.execute(select(Institution).order_by(Institution.name))
    institutions = result.scalars().all()
    return PipeflowResponse(
        success=True,
        data=[InstitutionResponse.model_validate(i) for i in institutions],
    )