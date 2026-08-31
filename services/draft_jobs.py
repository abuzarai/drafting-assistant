"""Async job store for slow draft generations.

The service runs single-instance, so an in-memory store is sufficient.
Jobs are TTL-swept (default 30 min); a job lost to a restart is recoverable —
the client simply resubmits.
"""

import asyncio
import threading
import time
import uuid


class JobStore:
    def __init__(self, ttl_seconds: int = 1800):
        self._ttl = ttl_seconds
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, run_coro, ttl_seconds: int | None = None) -> str:
        """Queue a coroutine as a background job. Returns the job id."""
        job_id = uuid.uuid4().hex
        with self._lock:
            self._sweep_locked()
            self._jobs[job_id] = {
                "status": "queued",
                "result": None,
                "error": None,
                "created": time.monotonic(),
                "ttl": ttl_seconds if ttl_seconds is not None else self._ttl,
            }
        asyncio.get_event_loop().create_task(self._run(job_id, run_coro))
        return job_id

    async def _run(self, job_id: str, run_coro):
        job = self.get_raw(job_id)
        if not job:
            return
        job["status"] = "running"
        try:
            job["result"] = await run_coro()
            job["status"] = "succeeded"
        except Exception as exc:  # noqa: BLE001 — status carries the error
            job["error"] = str(exc)
            job["status"] = "failed"

    def get_raw(self, job_id: str) -> dict | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            self._sweep_locked()
            job = self._jobs.get(job_id)
            if not job:
                return None
            return {
                "status": job["status"],
                "result": job["result"],
                "error": job["error"],
            }

    def _sweep_locked(self):
        now = time.monotonic()
        for jid in [k for k, j in self._jobs.items() if now - j["created"] > j["ttl"]]:
            del self._jobs[jid]


jobs = JobStore()