"""Media source adapters. Job state and persistent storage stay in the worker."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import urlsplit

import httpx
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.core.config import get_settings

logger = logging.getLogger("sunlena.media.extractors")


def _safe_label(value: object, fallback: str = "unknown") -> str:
    """Keep provider-supplied labels single-line and bounded for diagnostics."""
    label = re.sub(r"[^A-Za-z0-9_.-]", "_", str(value))[:64]
    return label or fallback


@dataclass(frozen=True)
class ExtractedMedia:
    path: Path
    title: str
    extension: str
    content_type: str | None = None
    source_bytes: int | None = None


class MediaExtractor(Protocol):
    def extract(self, source: str, title: str, artist: str, output_format: str,
                bitrate: str, scratch_dir: Path, max_file_bytes: int,
                progress: Callable[[int, str], None]) -> ExtractedMedia: ...


MAX_DURATION_SECONDS = 1800
YOUTUBE_DOMAINS = ("youtube.com", "youtu.be", "youtube-nocookie.com")
# yt-dlp's FFmpegExtractAudio codec names differ from file extensions for Vorbis.
_YTDLP_AUDIO_CODECS = {"mp3": "mp3", "m4a": "m4a", "opus": "opus", "ogg": "vorbis", "wav": "wav"}
# Prefer H.264/AAC in MP4, capped at 720p so typical music videos stay well
# below the 150 MB per-file limit. Fall back to any container and remux.
_YTDLP_MP4_FORMAT = (
    "bv*[ext=mp4][height<=720]+ba[ext=m4a]/b[ext=mp4][height<=720]/"
    "bv*[height<=720]+ba/b[height<=720]/bv*+ba/b"
)
_BOT_CHECK_MARKERS = ("confirm you", "not a bot", "http error 429", "too many requests")


def is_youtube_url(url: str | None) -> bool:
    if not url:
        return False
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return False
    return any(host == domain or host.endswith("." + domain) for domain in YOUTUBE_DOMAINS)


def choose_extractor(source_url: str | None) -> str:
    """Pick the backend for one job. Catalog jobs (no URL) are YouTube searches."""
    settings = get_settings()
    if settings.media_extractor == "yt-dlp":
        return "yt-dlp"
    if (source_url is None or is_youtube_url(source_url)) and settings.youtube_extractor == "yt-dlp":
        return "yt-dlp"
    return "cobalt"


def ytdlp_base_options() -> dict:
    """Options shared by every yt-dlp call (search and download)."""
    settings = get_settings()
    return {
        "quiet": True, "no_warnings": True, "noplaylist": True, "noprogress": True,
        "socket_timeout": 20, "retries": 3, "extractor_retries": 3,
        "cachedir": settings.ytdlp_cache_dir,
        # yt-dlp's Python API expects each extractor-arg value to be a list.
        # A bare string is iterated character by character, which silently
        # disables the bgutil PO-token provider.
        "extractor_args": {
            "youtubepot-bgutilhttp": {"base_url": [settings.ytdlp_pot_provider_url]},
        },
    }


def _friendly_ytdlp_error(exc: Exception) -> RuntimeError:
    message = re.sub(r"\x1b\[[0-9;]*m", "", str(exc)).removeprefix("ERROR: ").strip()
    lowered = message.lower()
    if any(marker in lowered for marker in _BOT_CHECK_MARKERS):
        return RuntimeError(
            "YouTube asked this server to prove it is not a bot (rate limited). "
            "Wait a few minutes and try again."
        )
    # Drop yt-dlp's cookie/FAQ boilerplate; keep the first sentence-ish part.
    message = message.split(" Use --cookies", 1)[0].split(" See  https://", 1)[0]
    return RuntimeError(f"yt-dlp could not download this media: {message[:300]}")


def _is_bot_check(exc: Exception) -> bool:
    lowered = str(exc).lower()
    return any(marker in lowered for marker in _BOT_CHECK_MARKERS)


def _estimated_bytes(info: dict) -> int | None:
    formats = info.get("requested_formats") or [info]
    total = 0
    for fmt in formats:
        size = fmt.get("filesize") or fmt.get("filesize_approx")
        if not size:
            return None
        total += int(size)
    return total


class YtDlpExtractor:
    """The yt-dlp/FFmpeg extractor, writing only into worker scratch space."""

    retry_delay_seconds = 8.0

    def extract(self, source: str, title: str, artist: str, output_format: str,
                bitrate: str, scratch_dir: Path, max_file_bytes: int,
                progress: Callable[[int, str], None]) -> ExtractedMedia:
        try:
            return self._extract(source, title, output_format, bitrate, scratch_dir,
                                 max_file_bytes, progress)
        except DownloadError as exc:
            if not _is_bot_check(exc):
                raise _friendly_ytdlp_error(exc) from exc
            logger.warning("ytdlp_bot_check_retry delay_seconds=%s", self.retry_delay_seconds)
            for leftover in scratch_dir.glob("*"):
                if leftover.is_file():
                    leftover.unlink(missing_ok=True)
            time.sleep(self.retry_delay_seconds)
            try:
                return self._extract(source, title, output_format, bitrate, scratch_dir,
                                     max_file_bytes, progress)
            except DownloadError as retry_exc:
                raise _friendly_ytdlp_error(retry_exc) from retry_exc

    def _extract(self, source: str, title: str, output_format: str, bitrate: str,
                 scratch_dir: Path, max_file_bytes: int,
                 progress: Callable[[int, str], None]) -> ExtractedMedia:
        last_update = [0.0]

        def on_progress(data: dict) -> None:
            if data.get("status") == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                percent = int(float(data.get("downloaded_bytes", 0)) * 90 / total) if total else 0
                now = time.monotonic()
                if now - last_update[0] >= 1.5:
                    progress(min(94, max(5, 5 + percent)), "Downloading source")
                    last_update[0] = now
            elif data.get("status") == "finished":
                progress(95, "Converting media")

        target_format = "mp3" if output_format == "auto" else output_format
        options: dict = {
            **ytdlp_base_options(),
            "format": _YTDLP_MP4_FORMAT if target_format == "mp4" else "bestaudio/best",
            "outtmpl": str(scratch_dir / "source.%(ext)s"),
            "max_filesize": max_file_bytes,
            "progress_hooks": [on_progress],
            "postprocessor_hooks": [lambda _: progress(97, "Finalizing file")],
        }
        if target_format == "mp4":
            options["merge_output_format"] = "mp4"
            options["postprocessors"] = [
                {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
                {"key": "FFmpegMetadata"},
            ]
        else:
            codec = _YTDLP_AUDIO_CODECS.get(target_format)
            if codec is None:
                raise RuntimeError("The selected output format is not supported.")
            options["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": codec,
                 "preferredquality": bitrate},
                {"key": "FFmpegMetadata"},
            ]
        with YoutubeDL(options) as ydl:
            # Resolve first so limits produce explicit errors. yt-dlp's own
            # match_filter/max_filesize skip silently, which used to surface as
            # a misleading "could not be converted" failure.
            info = ydl.extract_info(source, download=False)
            if info.get("_type") == "playlist" or "entries" in info:
                entries = [entry for entry in (info.get("entries") or []) if entry]
                if not entries:
                    raise RuntimeError("No matching YouTube source was found for this track.")
                info = entries[0]
            if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
                raise RuntimeError("Live streams and premieres cannot be downloaded.")
            duration = info.get("duration")
            if duration and duration > MAX_DURATION_SECONDS:
                raise RuntimeError("Source is longer than SunLena's 30-minute limit.")
            estimated = _estimated_bytes(info)
            if estimated and estimated > max_file_bytes:
                raise RuntimeError("The source media exceeds the 150 MB limit.")
            progress(5, "Downloading source")
            ydl.process_ie_result(info, download=True)
        expected_ext = "mp4" if target_format == "mp4" else target_format
        output = next(
            (path for path in scratch_dir.glob("*")
             if path.is_file() and path.suffix.lower() == f".{expected_ext}"),
            None,
        )
        if output is None:
            raise RuntimeError(
                f"yt-dlp finished without producing a {expected_ext.upper()} file "
                "(the source may exceed the 150 MB limit or have no compatible stream)."
            )
        return ExtractedMedia(output, str(info.get("title") or title)[:500], expected_ext)


def resolve_catalog_url(title: str, artist: str) -> tuple[str, str]:
    """Resolve a catalog entry to a public YouTube URL without downloading media."""
    options = {**ytdlp_base_options(), "extract_flat": "in_playlist", "skip_download": True}
    try:
        with YoutubeDL(options) as ydl:
            result = ydl.extract_info(f"ytsearch1:{title} {artist}", download=False)
    except DownloadError as exc:
        raise _friendly_ytdlp_error(exc) from exc
    entries = result.get("entries") or []
    if not entries or not entries[0].get("id"):
        raise RuntimeError("No matching YouTube source was found for this catalog result.")
    item = entries[0]
    url = f"https://www.youtube.com/watch?v={item['id']}"
    return url, str(item.get("title") or title)[:500]


def get_extractor(name: str) -> MediaExtractor:
    if name == "yt-dlp":
        return YtDlpExtractor()
    if name == "cobalt":
        return CobaltExtractor()
    raise ValueError("SUNLENA_MEDIA_EXTRACTOR must be 'yt-dlp' or 'cobalt'.")


class CobaltExtractor:
    """Downloads Cobalt's short-lived proxied result into worker scratch storage."""

    def __init__(self, client: httpx.Client | None = None):
        settings = get_settings()
        self.base_url = settings.cobalt_api_base_url.rstrip("/")
        self.token = (
            settings.cobalt_api_token.get_secret_value()
            if settings.cobalt_api_token else None
        )
        self.auth_scheme = settings.cobalt_auth_scheme
        self.timeout = settings.cobalt_request_timeout_seconds
        self.download_timeout = settings.cobalt_download_timeout_seconds
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(self.timeout, connect=10), follow_redirects=False
        )
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def extract(self, source_url: str, title: str, artist: str, output_format: str, bitrate: str,
                scratch_dir: Path, max_file_bytes: int,
                progress: Callable[[int, str], None]) -> ExtractedMedia:
        # Leave format selection to Cobalt's documented auto defaults. SunLena
        # inspects the returned file and only transcodes when the user explicitly
        # selected an output format in advanced settings.
        payload: dict[str, str | bool] = {"url": source_url, "alwaysProxy": True}
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        download_headers = {"Accept": "*/*"}
        if self.token:
            authorization = f"{self.auth_scheme} {self.token}"
            headers["Authorization"] = authorization
            download_headers["Authorization"] = authorization
        progress(10, "Requesting media from Cobalt")
        try:
            response = self.client.post(
                self.base_url, json=payload, headers=headers, timeout=self.timeout
            )
        except httpx.TimeoutException as exc:
            logger.error("cobalt_api_request_failed method=POST endpoint=/ reason=timeout timeout_seconds=%s", self.timeout)
            raise RuntimeError(
                f"Cobalt POST / timed out after {self.timeout:g} seconds ({type(exc).__name__})."
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("cobalt_api_request_failed method=POST endpoint=/ reason=transport exception=%s", type(exc).__name__)
            raise RuntimeError(f"Cobalt POST / transport error ({type(exc).__name__}).") from exc
        logger.info("cobalt_api_response method=POST endpoint=/ http_status=%s", response.status_code)
        if response.status_code in (401, 403):
            logger.error("cobalt_api_authentication_failed http_status=%s token_configured=%s", response.status_code, bool(self.token))
            raise RuntimeError(
                f"Cobalt POST / authentication failed (HTTP {response.status_code}; "
                f"token_configured={bool(self.token)})."
            )
        if response.is_error:
            content_type = response.headers.get("content-type", "unknown").split(";", 1)[0]
            logger.error("cobalt_api_http_error http_status=%s content_type=%s response_bytes=%s", response.status_code, content_type, len(response.content))
            raise RuntimeError(
                f"Cobalt POST / failed (HTTP {response.status_code}, "
                f"content-type={content_type}, response_bytes={len(response.content)})."
            )
        try:
            result = response.json()
        except ValueError as exc:
            content_type = response.headers.get("content-type", "unknown").split(";", 1)[0]
            logger.error("cobalt_api_invalid_json content_type=%s response_bytes=%s", content_type, len(response.content))
            raise RuntimeError(
                f"Cobalt POST / returned invalid JSON (content-type={content_type}, "
                f"response_bytes={len(response.content)})."
            ) from exc
        if not isinstance(result, dict):
            logger.error("cobalt_api_invalid_payload json_type=%s", type(result).__name__)
            raise RuntimeError(f"Cobalt POST / returned JSON type {type(result).__name__}, expected object.")
        api_status = _safe_label(result.get("status", "missing"))
        logger.info("cobalt_api_result status=%s", api_status)
        if result.get("status") == "error":
            error = result.get("error") or {}
            code = _safe_label(error.get("code", "unknown")) if isinstance(error, dict) else "unknown"
            context = error.get("context", {}) if isinstance(error, dict) else {}
            service = _safe_label(context.get("service")) if isinstance(context, dict) and context.get("service") else None
            suffix = f", service={service}" if service else ""
            logger.error("cobalt_api_extraction_error code=%s service=%s", code, service or "unknown")
            raise RuntimeError(f"Cobalt API extraction error code={code}{suffix}.")
        if result.get("status") != "tunnel" or not result.get("url"):
            status = api_status
            logger.error("cobalt_api_unsupported_result status=%s has_url=%s", status, bool(result.get("url")))
            raise RuntimeError(
                f"Cobalt POST / returned unsupported response status={status}; "
                "expected status=tunnel with a URL."
            )
        filename = str(result.get("filename") or title or "Media download")
        suffix = Path(filename).suffix.lower()
        if re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
            display_title = filename[: -len(suffix)].strip() or filename
        else:
            suffix = ".bin"
            display_title = filename
        destination = (scratch_dir / "cobalt-media").with_suffix(suffix)
        media_url = str(result["url"])
        # alwaysProxy should return a same-origin Cobalt tunnel URL. Never fetch arbitrary API output.
        media_parts = urlsplit(media_url)
        base_parts = urlsplit(self.base_url)
        if media_parts.netloc.lower() != base_parts.netloc.lower() or media_parts.scheme != base_parts.scheme:
            logger.error("cobalt_tunnel_rejected reason=unexpected_origin returned_host=%s expected_host=%s", media_parts.hostname or "missing", base_parts.hostname or "missing")
            raise RuntimeError(
                "Cobalt returned a tunnel on an unexpected host "
                f"(returned={media_parts.hostname or 'missing'}, expected={base_parts.hostname or 'missing'})."
            )
        download_status = 0
        try:
            timeout = httpx.Timeout(self.download_timeout, connect=10)
            with self.client.stream(
                "GET", media_url, headers=download_headers, timeout=timeout
            ) as download:
                download_status = download.status_code
                content_type = download.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                advertised_length = (
                    download.headers.get("content-length")
                    or download.headers.get("estimated-content-length")
                    or "unknown"
                )
                if not re.fullmatch(r"\d+", advertised_length):
                    advertised_length = "unknown"
                logger.info(
                    "cobalt_tunnel_response http_status=%s content_type=%s advertised_length=%s filename_extension=%s",
                    download.status_code, content_type or "unknown", advertised_length, suffix.lstrip(".") or "unknown",
                )
                if download.status_code != 200:
                    logger.error("cobalt_tunnel_http_error http_status=%s content_type=%s advertised_length=%s", download.status_code, content_type or "unknown", advertised_length)
                    raise RuntimeError(
                        f"Cobalt tunnel GET failed (HTTP {download.status_code}, "
                        f"content-type={content_type or 'unknown'}, "
                        f"advertised_length={advertised_length})."
                    )
                download.raise_for_status()
                total = 0
                with destination.open("wb") as output:
                    for chunk in download.iter_bytes(64 * 1024):
                        total += len(chunk)
                        if total > max_file_bytes:
                            logger.error("cobalt_tunnel_rejected reason=size_limit bytes_received=%s max_bytes=%s", total, max_file_bytes)
                            raise RuntimeError("The downloaded media exceeds the 150 MB limit.")
                        output.write(chunk)
        except RuntimeError:
            destination.unlink(missing_ok=True)
            raise
        except httpx.TimeoutException as exc:
            destination.unlink(missing_ok=True)
            logger.error("cobalt_tunnel_transfer_failed reason=timeout http_status=%s timeout_seconds=%s exception=%s", download_status or "not_received", self.download_timeout, type(exc).__name__)
            raise RuntimeError(
                f"Cobalt tunnel GET timed out after {self.download_timeout:g} seconds "
                f"(HTTP {download_status or 'not received'}, {type(exc).__name__})."
            ) from exc
        except httpx.HTTPError as exc:
            destination.unlink(missing_ok=True)
            logger.error("cobalt_tunnel_transfer_failed reason=transport http_status=%s exception=%s", download_status or "not_received", type(exc).__name__)
            raise RuntimeError(
                f"Cobalt tunnel GET transport failure (HTTP {download_status or 'not received'}, "
                f"{type(exc).__name__})."
            ) from exc
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        if not total:
            destination.unlink(missing_ok=True)
            logger.error("cobalt_tunnel_empty http_status=%s content_type=%s advertised_length=%s received_bytes=0", download_status, content_type or "unknown", advertised_length)
            raise RuntimeError(
                f"Cobalt returned an empty tunnel (HTTP {download_status}, "
                f"type={content_type or 'unknown'}, advertised length={advertised_length}). "
                "The source platform refused Cobalt's media request; for YouTube use "
                "SUNLENA_YOUTUBE_EXTRACTOR=yt-dlp."
            )
        if content_type in {"text/html", "application/json", "text/plain", "application/xml"}:
            destination.unlink(missing_ok=True)
            logger.error("cobalt_tunnel_non_media http_status=%s content_type=%s received_bytes=%s advertised_length=%s", download_status, content_type, total, advertised_length)
            raise RuntimeError(
                f"Cobalt tunnel returned a non-media content type "
                f"(HTTP {download_status}, type={content_type}, received_bytes={total}, "
                f"advertised_length={advertised_length})."
            )
        progress(94, "Preparing media file")
        if destination.stat().st_size > max_file_bytes:
            raise RuntimeError("The prepared file exceeds the 150 MB limit.")
        logger.info("cobalt_tunnel_download_complete http_status=%s content_type=%s received_bytes=%s filename_extension=%s", download_status, content_type or "unknown", total, destination.suffix.lstrip("."))
        return ExtractedMedia(
            destination, display_title[:500], destination.suffix.lstrip("."), content_type, total
        )
