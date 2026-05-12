import unittest

from app.services.resume import service


class _FakeBucket:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def upload(self, *, path: str, file: bytes, file_options: dict[str, str]) -> None:
        self.calls.append({"path": path, "file": file, "file_options": file_options})


class _FakeStorage:
    def __init__(self, bucket: _FakeBucket) -> None:
        self.bucket = bucket
        self.bucket_name: str | None = None

    def from_(self, bucket_name: str) -> _FakeBucket:
        self.bucket_name = bucket_name
        return self.bucket


class _FakeSupabaseClient:
    def __init__(self, storage: _FakeStorage) -> None:
        self.storage = storage


class _FakeArqPool:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def enqueue_job(self, name: str, **kwargs: object) -> None:
        self.calls.append({"name": name, **kwargs})


class ResumeServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_resume_to_storage_passes_raw_bytes_to_storage_client(self) -> None:
        bucket = _FakeBucket()
        storage = _FakeStorage(bucket)
        client = _FakeSupabaseClient(storage)

        original_get_client = service._get_supabase_client
        try:
            service._get_supabase_client = lambda: client
            storage_path = await service.upload_resume_to_storage(
                user_id=2,
                extension="pdf",
                file_bytes=b"resume-bytes",
            )
        finally:
            service._get_supabase_client = original_get_client

        self.assertEqual(storage.bucket_name, service.settings.SUPABASE_RESUMES_BUCKET)
        self.assertTrue(storage_path.startswith("2/"))
        self.assertTrue(storage_path.endswith(".pdf"))
        self.assertEqual(len(bucket.calls), 1)
        self.assertEqual(bucket.calls[0]["path"], storage_path)
        self.assertEqual(bucket.calls[0]["file"], b"resume-bytes")
        self.assertEqual(
            bucket.calls[0]["file_options"],
            {"content-type": "application/pdf", "upsert": "false"},
        )

    async def test_enqueue_resume_processing_includes_filename(self) -> None:
        arq_pool = _FakeArqPool()

        await service.enqueue_resume_processing(
            arq_pool=arq_pool,
            resume_id=11,
            file_bytes=b"resume-bytes",
            filename="resume.pdf",
        )

        self.assertEqual(
            arq_pool.calls,
            [
                {
                    "name": "process_resume",
                    "resume_id": 11,
                    "file_bytes": b"resume-bytes",
                    "filename": "resume.pdf",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
