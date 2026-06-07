"""
seed.py — Bootstrap script for PipeFlow.

Run once to create the NSFAS institution record and get the API key.
The API key is printed once and never stored — save it immediately.

Usage:
    python seed.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.models import Institution, InstitutionType, InstitutionStatus
from app.core.security import generate_api_key, hash_api_key


async def seed():
    async with AsyncSessionLocal() as session:
        # Check if NSFAS already exists
        result = await session.execute(
            select(Institution).where(Institution.institution_code == "NSFAS")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print("NSFAS institution already exists. Seed has already been run.")
            print(f"  ID:   {existing.id}")
            print(f"  Name: {existing.name}")
            print("  API key cannot be retrieved — it was shown only once at creation.")
            return

        # Create NSFAS
        raw_key = generate_api_key()
        nsfas = Institution(
            institution_code="NSFAS",
            name="National Student Financial Aid Scheme",
            type=InstitutionType.nsfas,
            api_key_hash=hash_api_key(raw_key),
            status=InstitutionStatus.active,
            contact_email="admin@nsfas.org.za",
        )
        session.add(nsfas)
        await session.commit()
        await session.refresh(nsfas)

        print("=" * 60)
        print("NSFAS institution created successfully.")
        print("=" * 60)
        print(f"  ID:               {nsfas.id}")
        print(f"  Institution Code: {nsfas.institution_code}")
        print(f"  Name:             {nsfas.name}")
        print(f"  Type:             {nsfas.type}")
        print()
        print("  API KEY (save this — it will not be shown again):")
        print(f"  {raw_key}")
        print("=" * 60)
        print()
        print("Use this key in the Authorization header:")
        print(f"  Authorization: Bearer {raw_key}")
        print()
        print("You can now use this key to:")
        print("  - Register universities via POST /api/v1/institutions")
        print("  - Submit outbound events via POST /api/v1/events/outbound")
        print("  - List all events via GET /api/v1/events")


if __name__ == "__main__":
    asyncio.run(seed())