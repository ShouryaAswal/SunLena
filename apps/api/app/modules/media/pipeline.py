"""Shared helpers for the media processing pipeline."""

import subprocess
from pathlib import Path


def safe_filename(value: str, max_length: int = 150) -> str:
    cleaned = "".join(char for char in value if char.isalnum() or char in " ._-()").strip(" .")
    return cleaned[:max_length] or "sunlena-track"


def normalize_cobalt_media(source: Path, output_format: str, bitrate: str,
                           scratch_dir: Path) -> Path:
    """Transcode Cobalt's auto-selected media only when a target was requested."""
    if output_format == "auto":
        return source

    target = scratch_dir / f"normalized.{output_format}"
    command = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(source)]
    if output_format == "mp4":
        command += [
            "-map", "0:v?", "-map", "0:a?", "-sn", "-dn",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", f"{bitrate}k", "-movflags", "+faststart",
        ]
    else:
        command += ["-vn"]
        codecs = {
            "mp3": ["-c:a", "libmp3lame", "-b:a", f"{bitrate}k"],
            "m4a": ["-c:a", "aac", "-b:a", f"{bitrate}k"],
            "opus": ["-c:a", "libopus", "-b:a", f"{bitrate}k"],
            "ogg": ["-c:a", "libvorbis", "-b:a", f"{bitrate}k"],
            "wav": ["-c:a", "pcm_s16le"],
        }
        codec = codecs.get(output_format)
        if codec is None:
            raise RuntimeError("The selected output format is not supported.")
        command += codec
    command.append(str(target))
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("FFmpeg timed out while converting the selected format.") from exc
    if result.returncode or not target.is_file() or not target.stat().st_size:
        detail = " ".join((result.stderr or "").split())[:180]
        raise RuntimeError(f"FFmpeg could not convert the media to {output_format.upper()}: {detail}")
    return target


def detect_media_extension(format_name: str, streams: list[dict], fallback: str) -> str:
    """Map FFprobe's detected container/codecs to a useful file extension."""
    names = set(format_name.lower().split(","))
    codecs = {str(stream.get("codec_name", "")).lower() for stream in streams}
    has_video = any(stream.get("codec_type") == "video" for stream in streams)
    if "mp3" in names:
        return "mp3"
    if "flac" in names:
        return "flac"
    if "wav" in names or "wav" in codecs:
        return "wav"
    if "ogg" in names:
        return "opus" if "opus" in codecs else "ogg"
    if "webm" in names:
        return "webm"
    if "matroska" in names:
        return "mkv"
    if names.intersection({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}):
        return "mp4" if has_video else "m4a"
    if "adts" in names or "aac" in names:
        return "aac"
    # Preserve Cobalt's sanitized filename extension for other FFprobe-readable
    # containers, rather than rejecting formats Cobalt adds in the future.
    return fallback if fallback.isalnum() and len(fallback) <= 8 else "bin"
