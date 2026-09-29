from pydantic import BaseModel


class TrackSummary(BaseModel):
    id: str
    title: str
    artist: str
    album: str | None = None
    duration_ms: int | None = None
    artwork_url: str | None = None
    source_url: str | None = None
    preview_url: str | None = None
    source: str


class SearchResponse(BaseModel):
    query: str
    results: list[TrackSummary]
    providers: dict[str, str]
