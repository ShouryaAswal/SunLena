from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PlaylistCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class PlaylistUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    visibility: Literal["private", "public"] | None = None


class AddTrack(BaseModel):
    track_id: UUID


class ReorderItems(BaseModel):
    item_ids: list[UUID] = Field(min_length=1, max_length=500)
