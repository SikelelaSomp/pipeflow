"""
API key authentication.
Every request from an institution must carry:
    Authorization: Bearer pf_<key>

NSFAS uses the same mechanism with its own institution record (type=nsfas).
"""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key
from app.db.session import get_db
from app.models.models import Institution, InstitutionStatus

bearer_scheme = HTTPBearer()


async def get_current_institution(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Institution:
    token = credentials.credentials

    result = await db.execute(
        select(Institution).where(Institution.status == InstitutionStatus.active)
    )
    institutions = result.scalars().all()

    # Linear scan with bcrypt verify — acceptable at low institution count (<30).
    # Replace with a token prefix lookup index if institution count grows significantly.
    for institution in institutions:
        if verify_api_key(token, institution.api_key_hash):
            return institution

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_nsfas(
    institution: Institution = Depends(get_current_institution),
) -> Institution:
    """Dependency that restricts an endpoint to NSFAS only."""
    from app.models.models import InstitutionType
    if institution.type != InstitutionType.nsfas:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is restricted to NSFAS",
        )
    return institution


async def require_university(
    institution: Institution = Depends(get_current_institution),
) -> Institution:
    """Dependency that restricts an endpoint to universities and TVET colleges."""
    from app.models.models import InstitutionType
    if institution.type == InstitutionType.nsfas:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for institutions, not NSFAS",
        )
    return institution