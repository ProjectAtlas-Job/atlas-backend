from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models.resume import Resume
from app.db.models.user import User
from app.db.models.user_settings import UserSettings
from app.db.session import AsyncSessionLocal
from app.services.profile.completeness import refresh_profile_completeness
from app.services.resume.embedder import embed
from app.services.resume.llm_enricher import enrich_resume_with_llm
from app.services.resume.parser import extract_text, normalise_text
from app.services.resume.scorer import semantic_score, structural_score


def _get_resume_format(filename: str) -> str:
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in {"pdf", "docx", "doc", "txt", "md"}:
        raise ValueError(f"Unsupported resume format: {filename}")
    return extension


async def get_user_settings_for_resume(session, resume_id: int) -> UserSettings:
    result = await session.execute(
        select(Resume)
        .options(selectinload(Resume.user).selectinload(User.settings))
        .where(Resume.id == resume_id)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise ValueError(f"Resume {resume_id} not found")
    if resume.user.settings is not None:
        return resume.user.settings
    return UserSettings(user_id=resume.user_id)


async def process_resume(
    ctx: dict[str, object],
    *,
    resume_id: int,
    file_bytes: bytes,
    filename: str,
) -> dict[str, object]:
    del ctx
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Resume).where(Resume.id == resume_id))
        resume = result.scalar_one_or_none()
        if resume is None:
            raise ValueError(f"Resume {resume_id} not found")

        now = datetime.now(UTC)
        resume.status = "processing"
        resume.updated_at = now
        await session.commit()

        try:
            format = _get_resume_format(filename)
            raw_text = await asyncio.to_thread(
                lambda: normalise_text(extract_text(file_bytes, format))
            )
            embedding = await asyncio.to_thread(embed, raw_text)
            s_score = await asyncio.to_thread(structural_score, raw_text)
            sem_score = await asyncio.to_thread(semantic_score, raw_text, embedding)
            try:
                user_settings = await get_user_settings_for_resume(session, resume_id)
                llm_output = await enrich_resume_with_llm(raw_text, user_settings)
                parsed_json = llm_output.model_dump(exclude={"ats_score", "ats_reasoning"})
                ats_score = llm_output.ats_score
            except Exception as exc:
                logger.warning("LLM enrichment failed for resume {}: {}", resume_id, exc)
                parsed_json = None
                ats_score = None

            resume.raw_text = raw_text
            resume.embedding = embedding
            resume.structural_score = s_score
            resume.semantic_score = sem_score
            resume.parsed_json = parsed_json
            resume.ats_score = ats_score
            resume.status = "completed"
            resume.updated_at = datetime.now(UTC)
            await session.flush()
            await refresh_profile_completeness(session, user_id=resume.user_id)
            await session.commit()
        except Exception:
            await session.rollback()
            resume.status = "error"
            resume.updated_at = datetime.now(UTC)
            await session.commit()
            logger.exception("Resume processing failed for resume_id={}", resume_id)
            raise

    return {"resume_id": resume_id, "status": "completed"}
