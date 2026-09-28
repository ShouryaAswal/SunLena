import hashlib
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.modules.catalog.models import Track
from app.modules.identity.auth import get_current_user
from app.modules.identity.models import User
from app.modules.playlists.models import Playlist, PlaylistItem
from app.modules.playlists.schemas import AddTrack, PlaylistCreate, PlaylistUpdate, ReorderItems
from app.modules.search.service import track_payload

router = APIRouter(prefix="/playlists", tags=["playlists"])


def _share_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _serialize(playlist: Playlist, share_token: str | None = None) -> dict:
    return {
        "id": str(playlist.id),
        "title": playlist.title,
        "description": playlist.description,
        "visibility": playlist.visibility,
        "created_at": playlist.created_at,
        "updated_at": playlist.updated_at,
        "share_token": share_token,
        "items": [
            {"id": str(item.id), "position": item.position, "track": track_payload(item.track)}
            for item in playlist.items
        ],
    }


def _owned_playlist(db: Session, owner_id: UUID, playlist_id: UUID) -> Playlist:
    playlist = db.execute(
        select(Playlist)
        .options(joinedload(Playlist.items).joinedload(PlaylistItem.track))
        .where(Playlist.id == playlist_id, Playlist.owner_id == owner_id)
    ).unique().scalar_one_or_none()
    if playlist is None:
        raise HTTPException(status_code=404, detail="Playlist not found.")
    return playlist


@router.get("")
def list_playlists(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    playlists = db.scalars(
        select(Playlist)
        .options(joinedload(Playlist.items).joinedload(PlaylistItem.track))
        .where(Playlist.owner_id == user.id)
        .order_by(Playlist.updated_at.desc())
    ).unique().all()
    return [_serialize(playlist) for playlist in playlists]


@router.post("", status_code=201)
def create_playlist(
    payload: PlaylistCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    playlist = Playlist(owner_id=user.id, title=payload.title.strip(), description=payload.description)
    if not playlist.title:
        raise HTTPException(status_code=422, detail="Playlist title cannot be blank.")
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return _serialize(playlist)


@router.get("/{playlist_id}")
def get_playlist(
    playlist_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return _serialize(_owned_playlist(db, user.id, playlist_id))


@router.patch("/{playlist_id}")
def update_playlist(
    playlist_id: UUID,
    payload: PlaylistUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    playlist = _owned_playlist(db, user.id, playlist_id)
    changes = payload.model_dump(exclude_unset=True)
    share_token = None
    for key, value in changes.items():
        if key == "title" and value is not None:
            value = value.strip()
            if not value:
                raise HTTPException(status_code=422, detail="Playlist title cannot be blank.")
        if key == "visibility" and value == "public":
            share_token = secrets.token_urlsafe(32)
            playlist.share_token_hash = _share_hash(share_token)
        elif key == "visibility" and value == "private":
            playlist.share_token_hash = None
        setattr(playlist, key, value)
    db.commit()
    return _serialize(_owned_playlist(db, user.id, playlist_id), share_token)


@router.delete("/{playlist_id}", status_code=204)
def delete_playlist(
    playlist_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    playlist = _owned_playlist(db, user.id, playlist_id)
    db.delete(playlist)
    db.commit()


@router.post("/{playlist_id}/items", status_code=201)
def add_track(
    playlist_id: UUID,
    payload: AddTrack,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    playlist = _owned_playlist(db, user.id, playlist_id)
    track = db.get(Track, payload.track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found. Search for it before adding it.")
    if any(item.track_id == track.id for item in playlist.items):
        return _serialize(playlist)
    next_position = db.scalar(
        select(func.coalesce(func.max(PlaylistItem.position), -1)).where(PlaylistItem.playlist_id == playlist.id)
    ) + 1
    db.add(PlaylistItem(playlist_id=playlist.id, track_id=track.id, position=next_position))
    db.commit()
    return _serialize(_owned_playlist(db, user.id, playlist_id))


@router.delete("/{playlist_id}/items/{item_id}", status_code=204)
def remove_track(
    playlist_id: UUID,
    item_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    playlist = _owned_playlist(db, user.id, playlist_id)
    item = next((entry for entry in playlist.items if entry.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Playlist item not found.")
    db.delete(item)
    db.flush()
    for position, entry in enumerate(sorted(playlist.items, key=lambda row: row.position)):
        if entry.id != item_id:
            entry.position = position
    db.commit()


@router.patch("/{playlist_id}/items/order")
def reorder_tracks(
    playlist_id: UUID,
    payload: ReorderItems,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    playlist = _owned_playlist(db, user.id, playlist_id)
    current = {item.id: item for item in playlist.items}
    if len(payload.item_ids) != len(current) or set(payload.item_ids) != set(current):
        raise HTTPException(status_code=422, detail="Reorder must include every playlist item exactly once.")
    for index, item_id in enumerate(payload.item_ids):
        current[item_id].position = -(index + 1)
    db.flush()
    for index, item_id in enumerate(payload.item_ids):
        current[item_id].position = index
    db.commit()
    return _serialize(_owned_playlist(db, user.id, playlist_id))


@router.get("/shared/{share_token}")
def get_shared_playlist(share_token: str, db: Session = Depends(get_db)) -> dict:
    playlist = db.execute(
        select(Playlist)
        .options(joinedload(Playlist.items).joinedload(PlaylistItem.track))
        .where(Playlist.share_token_hash == _share_hash(share_token), Playlist.visibility == "public")
    ).unique().scalar_one_or_none()
    if playlist is None:
        raise HTTPException(status_code=404, detail="Shared playlist not found.")
    return _serialize(playlist)
