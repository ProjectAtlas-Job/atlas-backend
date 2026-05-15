from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field
import instructor  # noqa: F401

from app.db.models.user_settings import UserSettings
from app.services.llm import call_llm


class ResumeParseOutput(BaseModel):
    skills: list[str] = Field(description="Normalised skill tags extracted from resume")
    recent_role: str = Field(description="Most recent job title and company, e.g. 'Senior Engineer at Acme'")
    education: str = Field(description="Highest qualification and institution")
    top_projects: list[str] = Field(description="Brief phrases describing top 3 projects")
    certifications: list[str] = Field(description="List of certifications if present")
    experience_years: int = Field(description="Total years of professional experience as integer")
    ats_score: float = Field(
        description=(
            "ATS compatibility score 0-100. Score based on: presence of standard sections, use of action verbs, "
            "quantifiable metrics, no tables/graphics/headers-footers, standard headings."
        )
    )
    ats_reasoning: str = Field(description="One sentence explaining the ATS score")


async def enrich_resume_with_llm(raw_text: str, user_settings: UserSettings) -> ResumeParseOutput:
    prompt = f"""Analyse this resume and extract structured information.

Resume text:
{raw_text[:6000]}

Extract: skills list, most recent role, education, top projects, certifications, experience years, and an ATS compatibility score (0-100)."""

    return await asyncio.to_thread(
        call_llm,
        prompt,
        user_settings=user_settings,
        response_model=ResumeParseOutput,
        temperature=0.0,
    )
