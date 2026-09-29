from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class DownloadCreate(BaseModel):
    track_id: UUID
    output_format: Literal["mp3", "m4a", "opus", "mp4"] = "mp3"
    bitrate: Literal["128", "192", "256", "320"] = "192"

    @model_validator(mode="after")
    def supported_format_quality(self):
        allowed = {"mp3": {"128", "192", "320"}, "m4a": {"128", "192", "256"},
                   "opus": {"128", "192", "256"}, "mp4": {"128", "192", "256", "320"}}
        if self.bitrate not in allowed[self.output_format]:
            raise ValueError("Choose a bitrate supported by the selected format.")
        return self


class MediaJobView(BaseModel):
    id: UUID
    track_id: UUID
    status: str
    stage: str
    progress: int = Field(ge=0, le=100)
    output_format: str
    bitrate: str
    title: str | None
    artist: str | None
    source_title: str | None
    file_name: str | None
    file_size: int | None
    error: str | None
    created_at: str
    finished_at: str | None
