from __future__ import annotations

import asyncio

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select

from app.core.config import settings
from app.db.models.resume import Resume
from app.db.session import AsyncSessionLocal


async def main() -> None:
    arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    queued = 0
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Resume).where(
                    Resume.status == "completed",
                    Resume.ats_score.is_(None),
                    Resume.deleted_at.is_(None),
                )
            )
            resumes = result.scalars().all()

        for resume in resumes:
            await arq_pool.enqueue_job(
                "process_resume",
                resume_id=resume.id,
                file_bytes=resume.file_data,
                filename=resume.filename,
            )
            queued += 1
    finally:
        await arq_pool.close()

    print(f"Queued {queued} resume enrichment jobs.")


if __name__ == "__main__":
    asyncio.run(main())
