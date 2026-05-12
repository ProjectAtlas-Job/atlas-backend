from arq.worker import run_worker
from arq.connections import RedisSettings

from app.core.config import settings
from app.worker.tasks import process_resume


class WorkerSettings:
    functions = [process_resume]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 300


if __name__ == "__main__":
    run_worker(WorkerSettings)
