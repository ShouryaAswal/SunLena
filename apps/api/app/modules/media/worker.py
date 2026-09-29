from __future__ import annotations

import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.modules.catalog.models import Track  # noqa: F401 - register FK target with Base.metadata.
from app.modules.identity.models import User  # noqa: F401 - register FK target with Base.metadata.
from app.modules.media.models import MediaJob
from app.modules.media.pipeline import download_from_catalog, safe_filename

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sunlena.media.worker")
settings = get_settings()


def set_progress(job_id, percent: int, stage: str) -> None:
    with SessionLocal() as db:
        db.execute(update(MediaJob).where(MediaJob.id == job_id, MediaJob.status == "running")
                   .values(progress=percent, stage=stage))
        db.commit()


def claim_job() -> MediaJob | None:
    with SessionLocal() as db:
        job = db.scalar(select(MediaJob).where(MediaJob.status == "queued")
                        .order_by(MediaJob.created_at).with_for_update(skip_locked=True).limit(1))
        if job is None:
            return None
        job.status = "running"
        job.stage = "Finding a matching source"
        job.progress = 1
        job.started_at = datetime.now(timezone.utc)
        db.commit()
        return job


def process(job: MediaJob) -> None:
    try:
        final_path, source_title, video_id = download_from_catalog(
            job.id, job.owner_id, job.title or "", job.artist or "", job.output_format,
            job.bitrate, Path(settings.media_root), settings.media_max_file_bytes,
            lambda percent, stage: set_progress(job.id, percent, stage),
        )
        stem = safe_filename(f"{job.title or source_title} - {job.artist or ''}")
        filename = f"{stem}.{job.output_format}"
        with SessionLocal() as db:
            current = db.get(MediaJob, job.id)
            if current:
                current.status = "completed"
                current.stage = "Ready to listen"
                current.progress = 100
                current.source_title = source_title
                current.file_path = str(final_path)
                current.file_name = filename
                current.file_size = final_path.stat().st_size
                current.finished_at = datetime.now(timezone.utc)
                db.commit()
        logger.info("Completed media job %s (%s)", job.id, video_id)
    except Exception as exc:
        logger.exception("Media job %s failed", job.id)
        with SessionLocal() as db:
            current = db.get(MediaJob, job.id)
            if current:
                current.status = "failed"
                current.stage = "Could not prepare this track"
                current.error = str(exc)[:500]
                current.finished_at = datetime.now(timezone.utc)
                db.commit()


def main() -> None:
    # Jobs interrupted by a host/container restart are safely retried from scratch.
    with SessionLocal() as db:
        db.execute(update(MediaJob).where(MediaJob.status == "running").values(
            status="queued", progress=0, stage="Waiting in queue", started_at=None,
            error=None,
        ))
        db.commit()
    # The only directories under the media root are worker scratch directories.
    root = Path(settings.media_root)
    root.mkdir(parents=True, exist_ok=True)
    for owner_dir in root.iterdir():
        if owner_dir.is_dir():
            for scratch in owner_dir.iterdir():
                if scratch.is_dir():
                    shutil.rmtree(scratch, ignore_errors=True)
    logger.info("Media worker polling the persistent job table")
    while True:
        job = claim_job()
        if job is None:
            time.sleep(2)
            continue
        process(job)


if __name__ == "__main__":
    main()
