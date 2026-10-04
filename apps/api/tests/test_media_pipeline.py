from pathlib import Path
import subprocess

from app.modules.media.pipeline import detect_media_extension, normalize_cobalt_media


def test_cobalt_default_preserves_original_file(tmp_path):
    source = tmp_path / "source.webm"
    source.write_bytes(b"source")
    assert normalize_cobalt_media(source, "auto", "192", tmp_path) == source


def test_selected_format_is_normalized_by_ffmpeg(tmp_path, monkeypatch):
    source = tmp_path / "source.webm"
    source.write_bytes(b"source")

    def fake_ffmpeg(command, **kwargs):
        Path(command[-1]).write_bytes(b"normalized")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("app.modules.media.pipeline.subprocess.run", fake_ffmpeg)
    output = normalize_cobalt_media(source, "mp3", "192", tmp_path)
    assert output.name == "normalized.mp3"
    assert output.read_bytes() == b"normalized"


def test_probe_detection_selects_actual_container_extension():
    assert detect_media_extension("mp3", [{"codec_type": "audio", "codec_name": "mp3"}], "bin") == "mp3"
    assert detect_media_extension("matroska,webm", [{"codec_type": "video", "codec_name": "vp9"}], "bin") == "webm"
    assert detect_media_extension("mov,mp4,m4a,3gp,3g2,mj2", [{"codec_type": "audio", "codec_name": "aac"}], "bin") == "m4a"
