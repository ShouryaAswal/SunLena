"""Regression tests for extractor routing and the yt-dlp adapter (no network)."""
from __future__ import annotations

from pathlib import Path

import pytest
from yt_dlp.utils import DownloadError

from app.modules.media import extractors
from app.modules.media.extractors import (
    YtDlpExtractor,
    choose_extractor,
    is_youtube_url,
    ytdlp_base_options,
)


class Settings:
    media_extractor = "cobalt"
    youtube_extractor = "yt-dlp"
    ytdlp_pot_provider_url = "http://bgutil-provider:4416"
    ytdlp_cache_dir = "/tmp/yt-dlp-cache"


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    current = Settings()
    monkeypatch.setattr(extractors, "get_settings", lambda: current)
    return current


@pytest.mark.parametrize("url, expected", [
    ("https://www.youtube.com/watch?v=abc", True),
    ("https://youtu.be/abc", True),
    ("https://music.youtube.com/watch?v=abc", True),
    ("https://m.youtube.com/shorts/abc", True),
    ("https://www.instagram.com/reels/abc/", False),
    ("https://notyoutube.com/watch?v=abc", False),
    ("https://youtube.com.evil.test/x", False),
    (None, False),
])
def test_is_youtube_url(url, expected):
    assert is_youtube_url(url) is expected


def test_cobalt_mode_routes_youtube_and_catalog_to_ytdlp(settings):
    assert choose_extractor("https://www.youtube.com/watch?v=abc") == "yt-dlp"
    assert choose_extractor(None) == "yt-dlp"  # catalog search
    assert choose_extractor("https://www.instagram.com/reels/abc/") == "cobalt"


def test_youtube_can_be_forced_to_cobalt(settings):
    settings.youtube_extractor = "cobalt"
    assert choose_extractor("https://youtu.be/abc") == "cobalt"
    assert choose_extractor(None) == "cobalt"


def test_ytdlp_mode_uses_ytdlp_for_everything(settings):
    settings.media_extractor = "yt-dlp"
    assert choose_extractor("https://www.instagram.com/reels/abc/") == "yt-dlp"


def test_pot_provider_url_is_passed_as_list():
    # A bare string is split into characters by yt-dlp, disabling bgutil.
    options = ytdlp_base_options()
    assert options["extractor_args"]["youtubepot-bgutilhttp"]["base_url"] == [
        "http://bgutil-provider:4416"
    ]
    assert options["cachedir"].startswith("/tmp")


class FakeYDL:
    """Minimal stand-in for yt_dlp.YoutubeDL that records options."""

    info: dict = {}
    errors: list[Exception] = []
    seen_options: list[dict] = []
    downloads = 0

    def __init__(self, options):
        self.options = options
        FakeYDL.seen_options.append(options)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, source, download=False):
        if FakeYDL.errors:
            raise FakeYDL.errors.pop(0)
        return FakeYDL.info

    def process_ie_result(self, info, download=True):
        FakeYDL.downloads += 1
        template = self.options["outtmpl"]
        codec = self.options.get("postprocessors", [{}])[0].get("preferredcodec")
        ext = {"vorbis": "ogg"}.get(codec, codec) or "mp4"
        Path(template.replace("%(ext)s", ext)).write_bytes(b"media")
        return info


@pytest.fixture
def fake_ydl(monkeypatch):
    FakeYDL.info = {"id": "abc", "title": "Mr. Brightside", "duration": 220}
    FakeYDL.errors = []
    FakeYDL.seen_options = []
    FakeYDL.downloads = 0
    monkeypatch.setattr(extractors, "YoutubeDL", FakeYDL)
    monkeypatch.setattr(YtDlpExtractor, "retry_delay_seconds", 0)
    return FakeYDL


def run(tmp_path, output_format="auto"):
    return YtDlpExtractor().extract(
        "https://youtu.be/abc", "", "", output_format, "192", tmp_path, 1000, lambda *_: None
    )


def test_ytdlp_auto_produces_mp3_and_keeps_dotted_title(tmp_path, fake_ydl):
    result = run(tmp_path)
    assert result.extension == "mp3"
    assert result.title == "Mr. Brightside"
    assert result.path.is_file()


def test_ogg_maps_to_vorbis_codec(tmp_path, fake_ydl):
    result = run(tmp_path, "ogg")
    assert fake_ydl.seen_options[0]["postprocessors"][0]["preferredcodec"] == "vorbis"
    assert result.extension == "ogg"


def test_mp4_uses_merging_selector(tmp_path, fake_ydl):
    result = run(tmp_path, "mp4")
    options = fake_ydl.seen_options[0]
    assert options["merge_output_format"] == "mp4"
    assert "bv*" in options["format"] and "best[ext=mp4]" != options["format"]
    assert result.extension == "mp4"


def test_long_source_fails_explicitly_without_download(tmp_path, fake_ydl):
    fake_ydl.info = {"id": "abc", "title": "Mix", "duration": 3600}
    with pytest.raises(RuntimeError, match="30-minute limit"):
        run(tmp_path)
    assert fake_ydl.downloads == 0


def test_oversized_source_fails_explicitly(tmp_path, fake_ydl):
    fake_ydl.info = {"id": "abc", "title": "Big", "duration": 60, "filesize": 5000}
    with pytest.raises(RuntimeError, match="150 MB"):
        run(tmp_path)


def test_empty_search_reports_no_match(tmp_path, fake_ydl):
    fake_ydl.info = {"_type": "playlist", "entries": []}
    with pytest.raises(RuntimeError, match="No matching YouTube source"):
        run(tmp_path)


def test_bot_check_is_retried_once_then_succeeds(tmp_path, fake_ydl):
    fake_ydl.errors = [DownloadError("ERROR: [youtube] abc: Sign in to confirm you’re not a bot.")]
    result = run(tmp_path)
    assert result.extension == "mp3"
    assert len(fake_ydl.seen_options) == 2


def test_persistent_bot_check_gives_friendly_error(tmp_path, fake_ydl):
    bot = "ERROR: [youtube] abc: Sign in to confirm you’re not a bot. Use --cookies for auth"
    fake_ydl.errors = [DownloadError(bot), DownloadError(bot)]
    with pytest.raises(RuntimeError, match="not a bot.*try again") as info:
        run(tmp_path)
    assert "--cookies" not in str(info.value)


def test_other_ytdlp_errors_are_not_retried(tmp_path, fake_ydl):
    fake_ydl.errors = [DownloadError("ERROR: [youtube] abc: Video unavailable")]
    with pytest.raises(RuntimeError, match="Video unavailable"):
        run(tmp_path)
    assert len(fake_ydl.seen_options) == 1
