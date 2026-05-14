from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.jobs import router as jobs_router
from app.api.v1.endpoints.resumes import router as resume_router
from app.api.v1.endpoints.scraper import router as scraper_router
from app.api.v1.endpoints.users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(jobs_router)
api_router.include_router(resume_router)
api_router.include_router(scraper_router)
api_router.include_router(users_router)
