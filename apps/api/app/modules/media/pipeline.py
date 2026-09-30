from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import Callable
from uuid import UUID

from yt_dlp import YoutubeDL

from app.core.config import get_settings


def safe_filename(value: str, max_length: int = 150) -> str:
    cleaned = "".join(char for char in value if char.isalnum() or char in " ._-()").strip(" .")
    return (cleaned[:max_length] or "sunlena-track")


def download_from_catalog(
    job_id: UUID,
    owner_id: UUID,
    title: str,
    artist: str,
    output_format: str,
    bitrate: str,
    media_root: Path,
    max_file_bytes: int,
    progress: Callable[[int, str], None],
) -> tuple[Path, str, str]:
    """Resolve one catalog item with yt-dlp search and convert it with FFmpeg."""
    owner_dir = media_root / str(owner_id)
    owner_dir.mkdir(parents=True, exist_ok=True)
    query = f"ytsearch1:{title} {artist}"
    with tempfile.TemporaryDirectory(prefix=f"{job_id}-", dir=owner_dir) as scratch:
        scratch_dir = Path(scratch)
        last_update = [0.0]

        def on_progress(data: dict) -> None:
            if data.get("status") == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                percent = int(float(data.get("downloaded_bytes", 0)) * 100 / total) if total else 0
                now = time.monotonic()
                if now - last_update[0] >= 1.5:
                    progress(min(94, max(0, percent)), "Downloading source")
                    last_update[0] = now
            elif data.get("status") == "finished":
                progress(96, "Converting audio")

        options: dict = {
            "format": "best[ext=mp4]" if output_format == "mp4" else "bestaudio/best",
            "outtmpl": str(scratch_dir / "source.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 20,
            "retries": 2,
            "extractor_retries": 2,
            "max_filesize": max_file_bytes,
            "match_filter": lambda info, *, incomplete: (
                "Source is longer than SunLena's 30-minute limit"
                if info.get("duration") and info["duration"] > 1800
                else None
            ),
            "progress_hooks": [on_progress],
            "postprocessor_hooks": [lambda _: progress(97, "Finalizing file")],
            "extractor_args": {
                "youtubepot-bgutilhttp": {
                    "base_url": get_settings().ytdlp_pot_provider_url,
                },
            },
        }
        if output_format != "mp4":
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": output_format,
                "preferredquality": bitrate,
            }, {"key": "FFmpegMetadata"}]

        with YoutubeDL(options) as ydl:
            result = ydl.extract_info(query, download=True)
            info = (result.get("entries") or [result])[0]
            source_title = str(info.get("title") or title)[:500]
            video_id = str(info.get("id") or job_id)

        candidates = [path for path in scratch_dir.glob("*") if path.is_file()]
        expected_ext = "mp4" if output_format == "mp4" else output_format
        output = next((path for path in candidates if path.suffix.lower() == f".{expected_ext}"), None)
        if output is None:
            raise RuntimeError("The source could not be converted to the selected format.")
        if output.stat().st_size > max_file_bytes:
            raise RuntimeError("The converted file exceeds the 150 MB limit.")

        final_path = owner_dir / f"{job_id}.{expected_ext}"
        shutil.move(str(output), final_path)
        return final_path, source_title, video_id
