import pytest
from pydantic import ValidationError

from app.modules.media.schemas import DownloadCreate


def test_download_accepts_catalog_track_or_public_url():
    assert DownloadCreate(track_id="d4710f6e-26a2-4e29-9784-987d5ed4d87a").track_id
    assert DownloadCreate(source_url="https://youtu.be/video").source_url == "https://youtu.be/video"
    assert DownloadCreate(source_url="https://youtu.be/video").output_format == "auto"
    assert DownloadCreate(source_url="https://youtu.be/video", output_format="mp3").output_format == "mp3"


@pytest.mark.parametrize("payload", [
    {},
    {"track_id": "d4710f6e-26a2-4e29-9784-987d5ed4d87a", "source_url": "https://youtu.be/video"},
    {"source_url": "http://youtube.com/watch?v=video"},
    {"source_url": "https://127.0.0.1/admin"},
    {"source_url": "https://youtube.com:5432/watch?v=video"},
    {"source_url": "https://example.com/video"},
    {"source_url": "https://user:password@youtube.com/video"},
])
def test_download_rejects_invalid_source(payload):
    with pytest.raises(ValidationError):
        DownloadCreate(**payload)
