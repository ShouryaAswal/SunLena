import asyncio
import time
from collections import deque
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.catalog.models import Track

APPLE_SEARCH_URL = "https://itunes.apple.com/search"
_CACHE_SECONDS = 300
_CACHE_CAPACITY = 256
_search_cache: dict[tuple[str, str, int], tuple[float, list[dict[str, Any]]]] = {}
_request_times: deque[float] = deque()
_request_lock = asyncio.Lock()


async def _reserve_provider_request() -> None:
    """Stay below Apple's documented approximate per-minute request ceiling."""
    now = time.monotonic()
    async with _request_lock:
        while _request_times and now - _request_times[0] >= 60:
            _request_times.popleft()
        if len(_request_times) >= 18:
            raise HTTPException(
                status_code=429,
                detail="Search is busy. Please wait a moment and try again.",
                headers={"Retry-After": "60"},
            )
        _request_times.append(now)


async def search_apple(
    query: str,
    limit: int = 24,
    field: str | None = None,
    exclude_explicit: bool = True,
) -> list[dict[str, Any]]:
    settings = get_settings()
    if field not in {None, "songTerm", "artistTerm", "albumTerm"}:
        raise ValueError("Unsupported Apple Search field.")
    key = (settings.apple_search_country.upper(), f"{query.strip().casefold()}|{field}|{exclude_explicit}", limit)
    cached = _search_cache.get(key)
    now = time.monotonic()
    if cached and now - cached[0] < _CACHE_SECONDS:
        return cached[1]
    await _reserve_provider_request()
    async with httpx.AsyncClient(timeout=httpx.Timeout(4.0, connect=2.0)) as client:
        params = {"term": query, "entity": "song", "limit": limit, "country": settings.apple_search_country}
        if field:
            params["attribute"] = field
        if exclude_explicit:
            params["explicit"] = "No"
        response = await client.get(APPLE_SEARCH_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    results: list[dict[str, Any]] = []
    for item in payload.get("results", []):
        external_id = item.get("trackId")
        title = item.get("trackName")
        artist = item.get("artistName")
        if not external_id or not title or not artist:
            continue
        results.append(
            {
                "source_key": f"apple:{external_id}",
                "title": title,
                "artist": artist,
                "album": item.get("collectionName"),
                "duration_ms": item.get("trackTimeMillis"),
                "artwork_url": item.get("artworkUrl100", "").replace("100x100", "600x600"),
                "source_url": item.get("trackViewUrl"),
                "provider": "apple",
            }
        )
    if len(_search_cache) >= _CACHE_CAPACITY:
        oldest_key = min(_search_cache, key=lambda item: _search_cache[item][0])
        del _search_cache[oldest_key]
    _search_cache[key] = (time.monotonic(), results)
    return results


def upsert_tracks(db: Session, results: list[dict[str, Any]]) -> list[Track]:
    tracks: list[Track] = []
    for result in results:
        track = db.scalar(select(Track).where(Track.source_key == result["source_key"]))
        if track is None:
            track = Track(**result)
            db.add(track)
        else:
            for field, value in result.items():
                setattr(track, field, value)
        tracks.append(track)
    db.commit()
    for track in tracks:
        db.refresh(track)
    return tracks


def track_payload(track: Track) -> dict[str, Any]:
    return {
        "id": str(track.id),
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "duration_ms": track.duration_ms,
        "artwork_url": track.artwork_url,
        "source_url": track.source_url,
        "source": track.provider,
    }


def find_track(db: Session, track_id: UUID) -> Track | None:
    return db.get(Track, track_id)
