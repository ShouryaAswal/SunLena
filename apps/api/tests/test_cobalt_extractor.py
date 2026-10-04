from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from app.modules.media.extractors import CobaltExtractor


class Settings:
    cobalt_api_base_url = "http://cobalt:9000/"
    cobalt_api_token = None
    cobalt_auth_scheme = "Api-Key"
    cobalt_request_timeout_seconds = 2
    cobalt_download_timeout_seconds = 3


@pytest.fixture(autouse=True)
def cobalt_settings(monkeypatch):
    monkeypatch.setattr("app.modules.media.extractors.get_settings", lambda: Settings())


def extractor(handler):
    transport = httpx.MockTransport(handler)
    return CobaltExtractor(httpx.Client(transport=transport))


def run_extract(client, destination, url="https://youtu.be/abc", bitrate="128", output_format="auto"):
    return client.extract(url, "", "", output_format, bitrate, destination, 100, lambda *_: None)


def test_tunnel_download_normalizes_metadata_and_auth(tmp_path):
    Settings.cobalt_api_token = SecretStr("test-token")
    seen = {}

    def handler(request):
        if request.method == "POST":
            seen["payload"] = request.read()
            seen["authorization"] = request.headers.get("Authorization")
            return httpx.Response(200, json={"status": "tunnel", "url": "http://cobalt:9000/tunnel/abc", "filename": "sample.mp3"})
        seen["download_authorization"] = request.headers.get("Authorization")
        seen["download_accept"] = request.headers.get("Accept")
        seen["download_content_type"] = request.headers.get("Content-Type")
        # The adapter test verifies Cobalt's HTTP handoff. Worker-level FFprobe
        # validation is responsible for proving the payload is playable media.
        return httpx.Response(200, content=b"audio", headers={"content-type": "audio/mpeg"})

    client = extractor(handler)
    result = run_extract(client, tmp_path, bitrate="192")
    assert result.path.read_bytes() == b"audio"
    assert result.title == "sample"
    assert result.content_type == "audio/mpeg"
    assert result.source_bytes == 5
    assert b'"url":"https://youtu.be/abc"' in seen["payload"]
    assert b'"alwaysProxy":true' in seen["payload"]
    assert b'"downloadMode"' not in seen["payload"]
    assert b'"audioFormat"' not in seen["payload"]
    assert seen["authorization"] == "Api-Key test-token"
    assert seen["download_authorization"] == "Api-Key test-token"
    assert seen["download_accept"] == "*/*"
    assert seen["download_content_type"] is None
    client.client.close()
    Settings.cobalt_api_token = None


def test_non_media_tunnel_response_is_rejected(tmp_path):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"status": "tunnel", "url": "http://cobalt:9000/tunnel/x", "filename": "sample.mp3"})
        return httpx.Response(200, text="upstream error page", headers={"content-type": "text/html"})

    client = extractor(handler)
    with pytest.raises(RuntimeError, match="non-media content type.*text/html"):
        run_extract(client, tmp_path)
    client.client.close()


def test_empty_tunnel_response_reports_response_metadata(tmp_path):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"status": "tunnel", "url": "http://cobalt:9000/tunnel/x", "filename": "sample.mp4"})
        return httpx.Response(200, content=b"", headers={"content-type": "application/octet-stream"})

    client = extractor(handler)
    with pytest.raises(RuntimeError, match="empty tunnel.*HTTP 200.*application/octet-stream"):
        run_extract(client, tmp_path)
    client.client.close()


def test_tunnel_http_failure_reports_status_and_content_type(tmp_path):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"status": "tunnel", "url": "http://cobalt:9000/tunnel/x", "filename": "sample.mp4"})
        return httpx.Response(502, text="upstream unavailable", headers={"content-type": "text/plain"})

    client = extractor(handler)
    with pytest.raises(RuntimeError, match="tunnel GET failed.*HTTP 502.*text/plain"):
        run_extract(client, tmp_path)
    client.client.close()


@pytest.mark.parametrize("body", [b"not json", b"[]"])
def test_malformed_response_is_rejected(body):
    client = extractor(lambda request: httpx.Response(200, content=body))
    with pytest.raises(RuntimeError, match="invalid JSON|expected object"):
        run_extract(client, Path("/tmp"))
    client.client.close()


def test_api_error_is_reported():
    client = extractor(lambda request: httpx.Response(200, json={"status": "error", "error": {"code": "youtube.login"}}))
    with pytest.raises(RuntimeError, match="youtube.login"):
        run_extract(client, Path("/tmp"))
    client.client.close()


def test_http_auth_failure_is_reported():
    client = extractor(lambda request: httpx.Response(401))
    with pytest.raises(RuntimeError, match="authentication failed.*HTTP 401"):
        run_extract(client, Path("/tmp"))
    client.client.close()


def test_http_failure_is_reported():
    client = extractor(lambda request: httpx.Response(500))
    with pytest.raises(RuntimeError, match="HTTP 500"):
        run_extract(client, Path("/tmp"))
    client.client.close()


def test_missing_url_and_unexpected_host_are_rejected():
    for body, message in [({"status": "tunnel"}, "expected status=tunnel with a URL"),
                          ({"status": "tunnel", "url": "https://attacker.test/file.mp3"}, "unexpected host")]:
        client = extractor(lambda request, body=body: httpx.Response(200, json=body))
        with pytest.raises(RuntimeError, match=message):
            run_extract(client, Path("/tmp"))
        client.client.close()


def test_timeout_is_reported():
    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)

    client = extractor(handler)
    with pytest.raises(RuntimeError, match="timed out"):
        run_extract(client, Path("/tmp"))
    client.client.close()
