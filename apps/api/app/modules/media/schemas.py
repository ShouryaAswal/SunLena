from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class DownloadCreate(BaseModel):
    track_id: UUID | None = None
    source_url: str | None = Field(default=None, max_length=2048)
    output_format: Literal["auto", "mp3", "m4a", "opus", "mp4", "ogg", "wav"] = "auto"
    bitrate: Literal["128", "192", "256", "320"] = "192"

    @model_validator(mode="after")
    def supported_format_quality(self):
        if (self.track_id is None) == (self.source_url is None):
            raise ValueError("Provide exactly one of track_id or source_url.")
        allowed_bitrates = {"128", "192", "256", "320"}
        allowed = {
            "auto": allowed_bitrates,
            "mp3": allowed_bitrates,
            "m4a": allowed_bitrates,
            "opus": allowed_bitrates,
            "ogg": allowed_bitrates,
            "wav": allowed_bitrates,
            "mp4": allowed_bitrates,
        }
        if self.bitrate not in allowed[self.output_format]:
            raise ValueError("Choose a bitrate supported by the selected format.")
        if self.source_url is not None:
            parts = urlsplit(self.source_url)
            if (
                parts.scheme != "https" or not parts.hostname or parts.username
                or parts.password or parts.port not in (None, 443)
            ):
                raise ValueError("Enter a public HTTPS media URL.")
            if not any(
                parts.hostname.lower() == domain
                or parts.hostname.lower().endswith("." + domain)
                for domain in (
                    "youtube.com", "youtu.be", "tiktok.com", "instagram.com", "facebook.com",
                    "fb.watch", "reddit.com", "redd.it", "twitter.com", "x.com", "soundcloud.com",
                    "vimeo.com", "twitch.tv", "pinterest.com", "pin.it", "bilibili.com", "b23.tv",
                    "dailymotion.com", "dai.ly", "tumblr.com", "vk.com", "ok.ru", "streamable.com",
                    "snapchat.com", "bluesky.app", "bsky.app", "newgrounds.com", "rutube.ru",
                    "loom.com", "on.soundcloud.com", "t.co",
                )
            ):
                raise ValueError("This URL host is not supported for direct downloads.")
        return self


class MediaJobView(BaseModel):
    id: UUID
    track_id: UUID | None
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
