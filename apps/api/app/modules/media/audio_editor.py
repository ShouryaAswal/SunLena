"""
audio_editor.py — Server-side audio processing using pydub + ffmpeg.

All functions accept/return pydub AudioSegment objects.
The main entry point `process_audio()` chains operations and exports.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Optional

from pydub import AudioSegment
from pydub.effects import low_pass_filter, high_pass_filter

log = logging.getLogger("sunlena.audio_editor")


# ── Edit parameters ──────────────────────────────────────────────────────────

@dataclass
class EditParams:
    trim_start_ms: int = 0
    trim_end_ms: Optional[int] = None        # None = end of track
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    bass_boost_db: float = 0.0               # +/- dB on low frequencies
    treble_boost_db: float = 0.0             # +/- dB on high frequencies
    volume_change_db: float = 0.0            # overall volume
    speed_factor: float = 1.0                # 0.5 – 2.0
    output_format: str = "mp3"               # mp3, wav, ogg, flac, aac
    output_quality: str = "192"              # bitrate for lossy formats


# ── Individual operations ────────────────────────────────────────────────────

def trim_audio(audio: AudioSegment, start_ms: int, end_ms: Optional[int]) -> AudioSegment:
    """Slice audio to [start_ms, end_ms]. If end_ms is None, go to the end."""
    if start_ms < 0:
        start_ms = 0
    if end_ms is None or end_ms > len(audio):
        end_ms = len(audio)
    if start_ms >= end_ms:
        raise ValueError("Trim end must be later than trim start.")
    return audio[start_ms:end_ms]


def apply_fade(audio: AudioSegment, fade_in_ms: int, fade_out_ms: int) -> AudioSegment:
    """Apply fade-in and/or fade-out."""
    if fade_in_ms > 0:
        fade_in_ms = min(fade_in_ms, len(audio))
        audio = audio.fade_in(fade_in_ms)
    if fade_out_ms > 0:
        fade_out_ms = min(fade_out_ms, len(audio))
        audio = audio.fade_out(fade_out_ms)
    return audio


def adjust_bass(audio: AudioSegment, boost_db: float) -> AudioSegment:
    """Boost or cut bass frequencies (below 300 Hz)."""
    if abs(boost_db) < 0.1:
        return audio
    low_freq = low_pass_filter(audio, cutoff=300) + boost_db
    rest = high_pass_filter(audio, cutoff=300)
    return rest.overlay(low_freq)


def adjust_treble(audio: AudioSegment, boost_db: float) -> AudioSegment:
    """Boost or cut treble frequencies (above 3000 Hz)."""
    if abs(boost_db) < 0.1:
        return audio
    high_freq = high_pass_filter(audio, cutoff=3000) + boost_db
    rest = low_pass_filter(audio, cutoff=3000)
    return rest.overlay(high_freq)


def adjust_volume(audio: AudioSegment, change_db: float) -> AudioSegment:
    """Adjust overall volume by the specified dB."""
    if abs(change_db) < 0.1:
        return audio
    return audio + change_db


def adjust_speed(audio: AudioSegment, factor: float) -> AudioSegment:
    """Speed up or slow down the audio. Factor: 0.5 = half speed, 2.0 = double.
    This changes pitch proportionally (chipmunk / slowed effect)."""
    if abs(factor - 1.0) < 0.01:
        return audio
    factor = max(0.5, min(2.0, factor))

    # Change sample rate to affect speed
    new_sample_rate = int(audio.frame_rate * factor)
    return audio._spawn(audio.raw_data, overrides={
        "frame_rate": new_sample_rate
    }).set_frame_rate(audio.frame_rate)


# ── Format configuration ────────────────────────────────────────────────────

FORMAT_CONFIG = {
    "mp3":  {"ext": "mp3",  "mime": "audio/mpeg",      "codec": "libmp3lame",   "lossy": True},
    "wav":  {"ext": "wav",  "mime": "audio/wav",        "codec": None,           "lossy": False},
    "ogg":  {"ext": "ogg",  "mime": "audio/ogg",        "codec": "libvorbis",    "lossy": True},
    "flac": {"ext": "flac", "mime": "audio/flac",       "codec": "flac",         "lossy": False},
    "aac":  {"ext": "aac",  "mime": "audio/aac",        "codec": "aac",          "lossy": True},
    "mp4":  {"ext": "mp4",  "mime": "video/mp4",       "codec": "aac",          "lossy": True},
}

QUALITY_OPTIONS = {
    "mp3":  ["128", "192", "320"],
    "ogg":  ["128", "192", "320"],
    "aac":  ["128", "192", "256"],
    "mp4":  ["128", "192", "256"],
    "wav":  ["lossless"],
    "flac": ["lossless"],
}


# ── Main processing pipeline ────────────────────────────────────────────────

def process_audio(file_bytes: bytes, params: EditParams) -> tuple[bytes, str, str]:
    """
    Full processing pipeline. Returns (processed_bytes, format_ext, mime_type).

    Steps applied in order:
    1. Trim
    2. Speed adjustment
    3. Bass boost
    4. Treble boost
    5. Volume
    6. Fade in / out
    7. Export to target format
    """
    log.info("Processing audio: format=%s, quality=%s", params.output_format, params.output_quality)

    # Load audio from bytes
    audio = AudioSegment.from_file(io.BytesIO(file_bytes))
    log.info("Loaded audio: duration=%dms, channels=%d, sample_rate=%d",
             len(audio), audio.channels, audio.frame_rate)

    # 1. Trim
    audio = trim_audio(audio, params.trim_start_ms, params.trim_end_ms)

    # 2. Speed
    audio = adjust_speed(audio, params.speed_factor)

    # 3. Bass
    audio = adjust_bass(audio, params.bass_boost_db)

    # 4. Treble
    audio = adjust_treble(audio, params.treble_boost_db)

    # 5. Volume
    audio = adjust_volume(audio, params.volume_change_db)

    # 6. Fade
    audio = apply_fade(audio, params.fade_in_ms, params.fade_out_ms)

    # 7. Export
    fmt = params.output_format.lower()
    fmt_config = FORMAT_CONFIG.get(fmt, FORMAT_CONFIG["mp3"])

    export_kwargs: dict = {"format": fmt_config["ext"]}

    if fmt_config["lossy"]:
        export_kwargs["bitrate"] = f"{params.output_quality}k"
    if fmt_config["codec"]:
        export_kwargs["codec"] = fmt_config["codec"]

    buf = io.BytesIO()
    audio.export(buf, **export_kwargs)
    result_bytes = buf.getvalue()

    log.info("Export complete: format=%s, size=%d bytes", fmt, len(result_bytes))
    return result_bytes, fmt_config["ext"], fmt_config["mime"]


# ── File size estimator ──────────────────────────────────────────────────────

def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def estimate_sizes(file_bytes: bytes) -> dict:
    """
    Estimate output file sizes for all format/quality combinations.
    Uses duration × bitrate for lossy, actual sample data size for lossless.
    """
    audio = AudioSegment.from_file(io.BytesIO(file_bytes))
    duration_sec = len(audio) / 1000.0
    channels = audio.channels
    sample_width = audio.sample_width  # bytes per sample
    sample_rate = audio.frame_rate

    estimates = {}

    for fmt, config in FORMAT_CONFIG.items():
        qualities = QUALITY_OPTIONS.get(fmt, ["192"])
        for quality in qualities:
            if quality == "lossless":
                if fmt == "wav":
                    # WAV: raw PCM = duration × sample_rate × channels × sample_width + header
                    size = int(duration_sec * sample_rate * channels * sample_width) + 44
                elif fmt == "flac":
                    # FLAC typically 50-70% of WAV size
                    wav_size = int(duration_sec * sample_rate * channels * sample_width)
                    size = int(wav_size * 0.6)
                else:
                    size = 0
                key = fmt
                label = f"{fmt.upper()} (lossless)"
            else:
                # Lossy: duration × bitrate_in_bytes
                bitrate_bps = int(quality) * 1000 / 8  # kbps → bytes/sec
                size = int(duration_sec * bitrate_bps)
                key = f"{fmt}_{quality}"
                label = f"{fmt.upper()} {quality}kbps"

            estimates[key] = {
                "format": fmt,
                "quality": quality,
                "label": label,
                "size_bytes": size,
                "size_human": _human_size(size),
            }

    return {
        "duration_seconds": round(duration_sec, 2),
        "duration_human": f"{int(duration_sec // 60)}:{int(duration_sec % 60):02d}",
        "estimates": estimates,
    }
