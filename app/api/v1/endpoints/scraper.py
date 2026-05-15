from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_arq_pool, get_current_active_user, get_db
from app.core.constants import MAJOR_JOB_BOARDS, MINOR_JOB_BOARDS
from app.core.rate_limiter import limiter, rate_limit_key
from app.db.models.user import User
from app.schemas.scraper import (
    ScraperRunAllResponse,
    ScraperRunRequest,
    ScraperRunResponse,
    ScraperStatusItem,
    ScraperStopResponse,
)
from app.services.scrapers.service import cancel_scraper_jobs, enqueue_scrape_job, list_running_scraper_jobs

router = APIRouter(prefix="/scraper", tags=["scraper"])


@router.post("/run", response_model=ScraperRunResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/minute", key_func=rate_limit_key)
async def run_scraper(
    request: Request,
    payload: ScraperRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    arq_pool: object = Depends(get_arq_pool),
) -> ScraperRunResponse:
    del request

    if payload.target_type != "jobs":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_type='contacts' is not available in this sprint.",
        )

    task_id = await enqueue_scrape_job(
        arq_pool=arq_pool,
        db=db,
        current_user=current_user,
        url=str(payload.url),
        source_type="manual",
        keywords=payload.keywords,
    )
    return ScraperRunResponse(task_id=task_id)


@router.post("/run-all", response_model=ScraperRunAllResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("20/hour", key_func=rate_limit_key)
async def run_all_scrapers(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    arq_pool: object = Depends(get_arq_pool),
) -> ScraperRunAllResponse:
    del request

    boards = MAJOR_JOB_BOARDS + MINOR_JOB_BOARDS
    sources: list[str] = []
    for board in boards:
        await enqueue_scrape_job(
            arq_pool=arq_pool,
            db=db,
            current_user=current_user,
            url=board["url"],
            source_type=board["source_type"],
        )
        sources.append(board["source_type"])

    return ScraperRunAllResponse(
        status="queued",
        queued_count=len(boards),
        sources=sources,
    )


@router.post("/stop", response_model=ScraperStopResponse)
async def stop_scraper(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    arq_pool: object = Depends(get_arq_pool),
) -> ScraperStopResponse:
    cancelled = await cancel_scraper_jobs(arq_pool=arq_pool, db=db, current_user=current_user)
    return ScraperStopResponse(cancelled=cancelled)


@router.get("/status", response_model=list[ScraperStatusItem])
async def get_scraper_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[ScraperStatusItem]:
    logs = await list_running_scraper_jobs(db=db, current_user=current_user)
    items: list[ScraperStatusItem] = []
    for log in logs:
        meta = log.meta if isinstance(log.meta, dict) else {}
        task_id = meta.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            continue
        url = meta.get("url")
        items.append(
            ScraperStatusItem(
                task_id=task_id,
                url=url if isinstance(url, str) else None,
                started_at=log.created_at,
                status=log.status,
            )
        )
    return items
