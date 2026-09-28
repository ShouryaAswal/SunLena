import asyncio
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.search.schemas import SearchResponse
from app.modules.search.service import search_apple, track_payload, upsert_tracks

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search_tracks(
    q: str = Query(min_length=1, max_length=120),
    field: Literal["all", "song", "artist", "album"] = "all",
    db: Session = Depends(get_db),
) -> dict:
    try:
        attribute = {"all": None, "song": "songTerm", "artist": "artistTerm", "album": "albumTerm"}[field]
        results = await search_apple(q, field=attribute)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Music search is temporarily unavailable.") from exc
    tracks = upsert_tracks(db, results)
    return {"query": q, "results": [track_payload(track) for track in tracks], "providers": {"apple": "ok"}}


@router.get("/discover")
async def discover(db: Session = Depends(get_db)) -> dict:
    themes = [
        {"id": "soft-focus", "title": "Soft focus", "query": "acoustic mellow"},
        {"id": "golden-hour", "title": "Golden hour", "query": "soul warm"},
        {"id": "after-hours", "title": "After hours", "query": "late night jazz"},
    ]
    async def load_section(theme: dict) -> dict:
        try:
            results = await search_apple(theme["query"], limit=6)
            tracks = upsert_tracks(db, results)
            return {**theme, "tracks": [track_payload(track) for track in tracks], "status": "ok"}
        except httpx.HTTPError:
            return {**theme, "tracks": [], "status": "unavailable"}

    return {"sections": await asyncio.gather(*(load_section(theme) for theme in themes))}
