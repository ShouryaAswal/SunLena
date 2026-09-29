from __future__ import annotations

import asyncio
import hashlib
import hmac
import mimetypes
import time
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.modules.catalog.models import Track
from app.modules.identity.auth import get_current_user
from app.modules.identity.models import User
from app.modules.media.models import MediaJob
from app.modules.media.pipeline import safe_filename
from app.modules.media.schemas import DownloadCreate

router = APIRouter(prefix="/media", tags=["media"])
ACTIVE_STATUSES = ("queued", "running")


def _serialize(job: MediaJob) -> dict:
    return {
        "id": str(job.id), "track_id": str(job.track_id), "status": job.status,
        "stage": job.stage, "progress": job.progress, "output_format": job.output_format,
        "bitrate": job.bitrate, "title": job.title, "artist": job.artist,
        "source_title": job.source_title, "file_name": job.file_name,
        "file_size": job.file_size, "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def _owned_job(db: Session, user_id: UUID, job_id: UUID) -> MediaJob:
    job = db.scalar(select(MediaJob).where(MediaJob.id == job_id, MediaJob.owner_id == user_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Download not found.")
    return job


def _existing_file(job: MediaJob) -> Path:
    if job.status != "completed" or not job.file_path:
        raise HTTPException(status_code=409, detail="This download is not ready yet.")
    root = Path(get_settings().media_root).resolve()
    path = Path(job.file_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail="The media file is no longer available.")
    return path


def _playback_signature(job: MediaJob, expires: int) -> str:
    secret = get_settings().media_signing_secret.encode()
    message = f"{job.id}:{job.owner_id}:{expires}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    rows = db.scalars(select(MediaJob).where(MediaJob.owner_id == user.id)
                      .order_by(MediaJob.created_at.desc()).limit(100)).all()
    return [_serialize(job) for job in rows]


@router.get("/jobs/{job_id}")
def get_job(job_id: UUID, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)) -> dict:
    return _serialize(_owned_job(db, user.id, job_id))


@router.post("/jobs", status_code=202)
def create_job(payload: DownloadCreate, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)) -> dict:
    track = db.get(Track, payload.track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Search for this track again before downloading it.")
    active = db.scalar(select(func.count()).select_from(MediaJob).where(
        MediaJob.owner_id == user.id, MediaJob.status.in_(ACTIVE_STATUSES))) or 0
    if active >= 2:
        raise HTTPException(status_code=429, detail="You already have two downloads in progress.")
    used_bytes = db.scalar(select(func.coalesce(func.sum(MediaJob.file_size), 0)).where(
        MediaJob.owner_id == user.id, MediaJob.status == "completed")) or 0
    settings = get_settings()
    if used_bytes + (active + 1) * settings.media_max_file_bytes > settings.media_max_user_bytes:
        raise HTTPException(status_code=413, detail="Your private library is full. Remove a download before adding another.")
    job = MediaJob(owner_id=user.id, track_id=track.id, title=track.title,
                   artist=track.artist, output_format=payload.output_format, bitrate=payload.bitrate)
    db.add(job)
    db.commit()
    db.refresh(job)
    return _serialize(job)


@router.get("/jobs/{job_id}/file")
def get_job_file(job_id: UUID, inline: bool = False, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> FileResponse:
    job = _owned_job(db, user.id, job_id)
    path = _existing_file(job)
    return FileResponse(path, filename=job.file_name or path.name,
                        media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                        content_disposition_type="inline" if inline else "attachment",
                        headers={"Cache-Control": "private, no-store"})


@router.post("/jobs/{job_id}/playback")
def create_playback_url(job_id: UUID, inline: bool = True, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)) -> dict:
    job = _owned_job(db, user.id, job_id)
    _existing_file(job)
    expires = int(time.time()) + 3600
    signature = _playback_signature(job, expires)
    return {"url": f"/api/v1/media/play/{job.id}?expires={expires}&signature={signature}&inline={str(inline).lower()}",
            "expires_at": expires}


@router.get("/play/{job_id}")
def play_media(job_id: UUID, expires: int, signature: str, inline: bool = True,
               db: Session = Depends(get_db)) -> FileResponse:
    if expires < int(time.time()) or expires > int(time.time()) + 3660:
        raise HTTPException(status_code=403, detail="This playback link has expired.")
    job = db.get(MediaJob, job_id)
    if job is None or not hmac.compare_digest(signature, _playback_signature(job, expires)):
        raise HTTPException(status_code=403, detail="This playback link is invalid.")
    path = _existing_file(job)
    return FileResponse(path, filename=job.file_name or path.name,
                        media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                        content_disposition_type="inline" if inline else "attachment",
                        headers={"Cache-Control": "private, no-store"})


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: UUID, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)) -> Response:
    job = _owned_job(db, user.id, job_id)
    if job.status == "running":
        raise HTTPException(status_code=409, detail="This download is running; try again when it finishes.")
    if job.file_path:
        path = Path(job.file_path).resolve()
        root = Path(get_settings().media_root).resolve()
        if path.is_relative_to(root) and path.is_file():
            path.unlink()
    db.delete(job)
    db.commit()
    return Response(status_code=204)


@router.post("/edit")
async def edit_audio(
    job_id: UUID = Form(...),
    trim_start_ms: int = Form(0, ge=0, le=1800000),
    trim_end_ms: int = Form(-1, ge=-1, le=1800000),
    fade_in_ms: int = Form(0, ge=0, le=30000),
    fade_out_ms: int = Form(0, ge=0, le=30000),
    bass_boost_db: float = Form(0, ge=-12, le=12),
    treble_boost_db: float = Form(0, ge=-12, le=12),
    volume_change_db: float = Form(0, ge=-24, le=12),
    speed_factor: float = Form(1, ge=0.5, le=2),
    output_format: str = Form("mp3"),
    output_quality: str = Form("192"),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> Response:
    job = _owned_job(db, user.id, job_id)
    path = _existing_file(job)
    if path.stat().st_size > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Editor source is limited to 50 MB.")
    supported = {"mp3": {"128", "192", "320"}, "aac": {"128", "192", "256"},
                 "ogg": {"128", "192", "320"}, "mp4": {"128", "192", "256"},
                 "wav": {"lossless"}, "flac": {"lossless"}}
    if output_format not in supported or output_quality not in supported[output_format]:
        raise HTTPException(status_code=422, detail="Choose a supported audio format and quality.")
    from app.modules.media.audio_editor import EditParams, process_audio

    def render() -> tuple[bytes, str, str]:
        source = path.read_bytes()
        params = EditParams(
            trim_start_ms=trim_start_ms,
            trim_end_ms=trim_end_ms if trim_end_ms >= 0 else None,
            fade_in_ms=fade_in_ms, fade_out_ms=fade_out_ms,
            bass_boost_db=bass_boost_db, treble_boost_db=treble_boost_db,
            volume_change_db=volume_change_db, speed_factor=speed_factor,
            output_format=output_format, output_quality=output_quality,
        )
        return process_audio(source, params)

    try:
        output, extension, content_type = await asyncio.to_thread(render)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="The editor could not process this file.") from exc
    if len(output) > get_settings().media_max_file_bytes:
        raise HTTPException(status_code=413, detail="Edited output exceeds the 150 MB limit.")
    stem = safe_filename(f"{job.title or 'SunLena track'} - edited")
    return Response(content=output, media_type=content_type,
                    headers={"Content-Disposition": f'attachment; filename="{stem}.{extension}"'})
