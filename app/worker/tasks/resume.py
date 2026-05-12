from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.models.resume import Resume
from app.db.session import AsyncSessionLocal
from app.services.profile.completeness import refresh_profile_completeness
from app.services.resume.embedder import embed
from app.services.resume.parser import extract_text, normalise_text
from app.services.resume.scorer import semantic_score, structural_score
from loguru import logger


async def process_resume(ctx: dict[str, object], *, resume_id: int, file_bytes: bytes) -> None:
    del ctx
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Resume).where(Resume.id == resume_id))
        resume = result.scalar_one_or_none()
        if resume is None:
            logger.warning("Resume {} not found for processing", resume_id)
            return

        resume.status = "processing"
        await session.commit()

        try:
            raw_text = await asyncio.to_thread(
                lambda: normalise_text(extract_text(file_bytes, resume.format))
            )
            embedding = await asyncio.to_thread(embed, raw_text)
            structural = await asyncio.to_thread(structural_score, raw_text)
            semantic = await asyncio.to_thread(semantic_score, raw_text, embedding)
            resume.raw_text = raw_text
            resume.embedding = embedding
            resume.structural_score = structural
            resume.semantic_score = semantic
            resume.status = "completed"
            await session.flush()
            await refresh_profile_completeness(session, user_id=resume.user_id)
            await session.commit()
        except Exception:
            await session.rollback()
            resume.status = "error"
            await session.commit()
            logger.exception("Resume processing failed for resume_id={}", resume_id)
            raise
