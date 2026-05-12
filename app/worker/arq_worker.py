from app.worker.tasks import process_resume


class WorkerSettings:
    functions = [process_resume]
