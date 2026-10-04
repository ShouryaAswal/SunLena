from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select, update

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.modules.catalog.models import Track  # noqa: F401 - register FK target with Base.metadata.
from app.modules.identity.models import User  # noqa: F401 - register FK target with Base.metadata.
from app.modules.media.models import MediaJob
from app.modules.media.extractors import choose_extractor, get_extractor, resolve_catalog_url
from app.modules.media.pipeline import detect_media_extension, normalize_cobalt_media, safe_filename

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sunlena.media.worker")
# Cobalt tunnel URLs contain short-lived signature parameters. httpx's INFO
# request log includes full URLs, so keep those query parameters out of logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
settings = get_settings()


def _safe_diagnostic(message: str, source_url: str | None) -> str:
    """Remove source URLs and control characters before writing errors to logs/UI."""
    if source_url:
        message = message.replace(source_url, "[source URL]")
        query = source_url.partition("?")[2].partition("#")[0]
        if query:
            message = message.replace(query, "[URL parameters]")
    message = re.sub(r"https?://[^\s\"'<>]+", "[redacted URL]", message)
    return " ".join(message.split())[:500]


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
        job.stage = "Preparing your media URL" if job.source_url else "Finding a matching source"
        job.progress = 1
        job.started_at = datetime.now(timezone.utc)
        db.commit()
        return job


def process(job: MediaJob) -> None:
    stage_context = ["Starting media job"]
    source_for_diagnostics: str | None = job.source_url
    extractor_name = choose_extractor(job.source_url)
    try:
        def progress(percent: int, stage: str) -> None:
            stage_context[0] = stage
            set_progress(job.id, percent, stage)

        source = job.source_url or f"ytsearch1:{job.title or ''} {job.artist or ''}"
        title = job.title or ""
        if extractor_name == "cobalt" and job.source_url is None:
            stage_context[0] = "Resolving catalog track URL with yt-dlp"
            source, title = resolve_catalog_url(job.title or "", job.artist or "")
        source_for_diagnostics = source if source.startswith("http") else None
        try:
            source_host = urlsplit(source_for_diagnostics or "").hostname or "catalog-search"
        except ValueError:
            source_host = "invalid-url"
        logger.info(
            "media_job_started job_id=%s extractor=%s requested_format=%s source_host=%s source_type=%s",
            job.id, extractor_name, job.output_format, source_host,
            "direct-url" if job.source_url else "catalog-search",
        )
        owner_dir = Path(settings.media_root) / str(job.owner_id)
        owner_dir.mkdir(parents=True, exist_ok=True)
        extractor = get_extractor(extractor_name)
        stage_context[0] = f"Extracting media with {extractor_name}"
        with tempfile.TemporaryDirectory(prefix=f"{job.id}-", dir=owner_dir) as scratch:
            try:
                extracted = extractor.extract(
                    source, title, job.artist or "", job.output_format, job.bitrate,
                    Path(scratch), settings.media_max_file_bytes, progress,
                )
            finally:
                close = getattr(extractor, "close", None)
                if close:
                    close()
            media_path = extracted.path
            if extractor_name == "cobalt" and job.output_format != "auto":
                stage_context[0] = f"Converting to {job.output_format.upper()} with FFmpeg"
                progress(94, stage_context[0])
                media_path = normalize_cobalt_media(
                    media_path, job.output_format, job.bitrate, Path(scratch)
                )
            stage_context[0] = "Validating extracted media with FFprobe"
            progress(96, "Checking media file")
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries",
                     "format=duration,format_name:stream=codec_type,codec_name", "-of", "json",
                     str(media_path)],
                    capture_output=True, text=True, timeout=15,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("FFprobe timed out while validating the extracted media (15 seconds).") from exc
            except OSError as exc:
                raise RuntimeError(f"FFprobe could not start ({type(exc).__name__}); verify FFmpeg is installed in the worker image.") from exc
            if probe.returncode:
                # Keep FFprobe's useful diagnosis instead of flattening every bad
                # extractor response into the same message. Do not expose scratch
                # paths in the user-facing error.
                detail = " ".join((probe.stderr or "").split())
                detail = detail.replace(str(media_path), "[temporary media file]")
                detail = detail[:180] or "FFprobe returned an error without details"
                source_info = ""
                if extracted.content_type or extracted.source_bytes is not None:
                    source_info = (
                        f" (Cobalt response: {extracted.content_type or 'unknown content type'}, "
                        f"{extracted.source_bytes if extracted.source_bytes is not None else 'unknown'} bytes)"
                    )
                raise RuntimeError(f"The extracted file is not readable media{source_info}: {detail}")
            try:
                probed = json.loads(probe.stdout)
                duration = float(probed["format"]["duration"])
                streams = probed.get("streams", [])
                detected_format = str(probed["format"].get("format_name", ""))
            except (ValueError, KeyError, TypeError) as exc:
                raise RuntimeError("The extracted media duration could not be verified.") from exc
            if job.output_format == "mp4" and not any(
                stream.get("codec_type") == "video" for stream in streams
            ):
                raise RuntimeError("MP4 video was selected, but the source contains no video stream.")
            if duration > 1800:
                raise RuntimeError("Source is longer than SunLena's 30-minute limit.")
            if media_path.stat().st_size > settings.media_max_file_bytes:
                raise RuntimeError("The prepared file exceeds the 150 MB limit.")
            if extractor_name == "cobalt" and job.output_format == "auto":
                actual_format = detect_media_extension(detected_format, streams, extracted.extension)
            elif job.output_format != "auto":
                actual_format = job.output_format
            else:
                actual_format = extracted.extension
            final_path = owner_dir / f"{job.id}.{actual_format}"
            stage_context[0] = "Moving validated media into private storage"
            shutil.move(str(media_path), final_path)
            source_title = extracted.title
        # Extractors return display titles without file extensions; do not use
        # Path().stem here, which truncates titles such as "Mr. Brightside".
        display_title = job.title if job.track_id else (source_title or "SunLena download")
        stem = safe_filename(" - ".join(part for part in (display_title, job.artist) if part))
        filename = f"{stem}.{actual_format}"
        stage_context[0] = "Saving completed media job"
        with SessionLocal() as db:
            current = db.get(MediaJob, job.id)
            if current is None:
                # The user removed the queued job while it was running.
                final_path.unlink(missing_ok=True)
                logger.info("media_job_deleted_during_processing job_id=%s", job.id)
                return
            current.status = "completed"
            current.stage = "Ready to listen"
            current.progress = 100
            current.source_title = source_title[:500] if source_title else None
            if current.source_url and source_title:
                current.title = source_title[:500]
            current.output_format = actual_format
            current.file_path = str(final_path)
            current.file_name = filename
            current.file_size = final_path.stat().st_size
            current.finished_at = datetime.now(timezone.utc)
            db.commit()
        logger.info(
            "media_job_completed job_id=%s extractor=%s format=%s bytes=%s",
            job.id, extractor_name, actual_format, final_path.stat().st_size,
        )
    except Exception as exc:
        error_message = _safe_diagnostic(str(exc), source_for_diagnostics or job.source_url)
        try:
            source_host = urlsplit(source_for_diagnostics or "").hostname or "catalog-search"
        except ValueError:
            source_host = "unknown"
        logger.error(
            "media_job_failed job_id=%s extractor=%s stage=%r source_host=%s "
            "exception=%s detail=%s",
            job.id, extractor_name, stage_context[0], source_host,
            type(exc).__name__, error_message,
        )
        try:
            with SessionLocal() as db:
                current = db.get(MediaJob, job.id)
                if current:
                    current.status = "failed"
                    current.stage = "Could not prepare this media"
                    current.error = error_message[:500]
                    current.finished_at = datetime.now(timezone.utc)
                    db.commit()
        except Exception as persist_exc:
            logger.error(
                "media_job_failure_state_persist_failed job_id=%s exception=%s detail=%s",
                job.id, type(persist_exc).__name__,
                _safe_diagnostic(str(persist_exc), None),
            )


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
        try:
            job = claim_job()
        except Exception as exc:
            logger.error(
                "media_job_claim_failed exception=%s detail=%s",
                type(exc).__name__, _safe_diagnostic(str(exc), None),
            )
            time.sleep(5)
            continue
        if job is None:
            time.sleep(2)
            continue
        process(job)


if __name__ == "__main__":
    main()
