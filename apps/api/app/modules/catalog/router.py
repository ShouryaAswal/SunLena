from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.search.service import find_track, track_payload

router = APIRouter(prefix="/tracks", tags=["tracks"])


@router.get("/{track_id}")
def get_track(track_id: UUID, db: Session = Depends(get_db)) -> dict:
    track = find_track(db, track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found.")
    return track_payload(track)
