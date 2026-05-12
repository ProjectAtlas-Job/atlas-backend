from arq.connections import RedisSettings

from app.core.config import settings
from app.worker.tasks import process_resume


class WorkerSettings:
    functions = [process_resume]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
