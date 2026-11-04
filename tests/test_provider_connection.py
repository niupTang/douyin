import io
import json
import urllib.error
from unittest.mock import Mock

import pytest
from flask import Flask

from backend_app.agent.errors import ProviderAuthenticationError
from backend_app.agent.providers.openai_compatible import OpenAICompatibleProviderAdapter
from backend_app.agent.secret_store import MemoryMasterKeyProvider, SecretStore
from backend_app.modules.ai_settings import AiSettingsService
from backend_app.modules.ai_settings.routes import create_ai_settings_blueprint
from backend_app.modules.idea_radar.pipeline import run_pipeline


class JsonResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps({"data": [{"id": "mock-model"}]}).encode("utf-8")


@pytest.mark.parametrize("base_url", ["https://example.invalid", "https://example.invalid/v1/"])
def test_connection_uses_saved_key_and_single_api_version(tmp_path, monkeypatch, base_url):
    service = AiSettingsService(tmp_path / "settings.db", secret_store=SecretStore(MemoryMasterKeyProvider()))
    service.save_provider({"name": "Test", "providerType": "openai_compatible", "baseUrl": base_url}, "test")
    service.set_credential("test", "sk-private")

    def open_request(request, timeout):
        assert request.full_url == "https://example.invalid/v1/models"
        assert request.get_method() == "GET"
        assert request.get_header("Authorization") == "Bearer sk-private"
        assert timeout == 20
        return JsonResponse()

    monkeypatch.setattr("urllib.request.urlopen", open_request)
    app = Flask(__name__)
    app.register_blueprint(create_ai_settings_blueprint(lambda: service))
    response = app.test_client().post("/api/ai/providers/test/test")
    assert response.status_code == 200
    assert response.get_json()["data"] == {"connected": True, "modelCount": 1}
    assert b"sk-private" not in response.data


@pytest.mark.parametrize("status", [401, 403])
def test_provider_auth_failure_identifies_provider_without_exposing_secret(monkeypatch, status):
    def reject(request, **_):
        raise urllib.error.HTTPError(request.full_url, status, "rejected", {}, io.BytesIO(b'sk-private'))

    monkeypatch.setattr("urllib.request.urlopen", reject)
    service = Mock()
    service.test_provider_connection.side_effect = lambda _: OpenAICompatibleProviderAdapter(
        {"name": "DeepSeek", "base_url": "https://example.invalid"}, {}, "sk-private"
    ).check_connection()
    app = Flask(__name__)
    app.register_blueprint(create_ai_settings_blueprint(lambda: service))
    response = app.test_client().post("/api/ai/providers/test/test")
    assert response.status_code == 400
    assert response.get_json()["errorCode"] == "provider_authentication_error"
    assert "DeepSeek" in response.get_json()["message"]
    assert str(status) in response.get_json()["message"]
    assert b"sk-private" not in response.data


def test_analysis_retry_keeps_cached_transcript_and_skips_download():
    cached = {"cleaned_transcript": "已保存的视频正文", "stage": "analyzing", "progress_percent": 84}
    download = Mock()
    transcribe = Mock()
    download_root = Mock()
    update = Mock()
    registry = Mock()
    registry.is_cancelled.return_value = False
    run_pipeline(
        1, "定位", load_video=lambda _: {"video_url": "https://example.invalid/video"},
        get_transcript=lambda _: cached, update_progress=update, download_video=download,
        transcribe_media=transcribe, clean_transcript=Mock(), build_prompt=lambda *_: "prompt",
        schema_factory=lambda: {}, run_structured=Mock(side_effect=ProviderAuthenticationError("rejected")),
        get_agent_model=Mock(), parse_metric_number=Mock(), registry=registry, get_download_root=download_root,
    )
    download.assert_not_called()
    transcribe.assert_not_called()
    download_root.assert_not_called()
    assert update.call_args.kwargs["status"] == "failed"
    assert update.call_args.kwargs["analysis_basis"] == "transcript"
    assert all("cleaned_transcript" not in call.kwargs for call in update.call_args_list)
    registry.finish.assert_called_once_with(1)
