import json
import logging

from fastapi.testclient import TestClient

from afterstory.api import create_app
from afterstory.config import Settings
from afterstory.diagnostics import diagnose
from afterstory.domain import ProviderError


def test_diagnostics_are_useful_and_redacted(database):
    cfg, _ = database
    secret = "diagnostic-secret-must-not-appear"
    settings = Settings(
        _env_file=None,
        database_url=cfg.database_url,
        dev_user_id=cfg.dev_user_id,
        llm_active_model="deepseek",
        llm_models={"deepseek": {"api_key": secret}},
    )
    result = diagnose(settings)
    rendered = json.dumps(result)
    assert result["ok"] is True
    assert result["configuration"]["model_credentials_configured"] is True
    assert result["database"]["reachable"] is True
    assert result["migration"]["current"] is True
    assert secret not in rendered
    assert "postgresql" not in rendered
    assert "search_path" not in rendered

    missing_key = Settings(
        _env_file=None,
        database_url=cfg.database_url,
        llm_active_model="deepseek",
        llm_models={"deepseek": {"api_key": ""}},
    )
    missing_result = diagnose(missing_key)
    assert missing_result["configuration"]["valid"] is True
    assert missing_result["configuration"]["model_credentials_configured"] is False
    assert missing_result["database"]["reachable"] is True
    assert missing_result["ok"] is False

    unreachable = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://hidden:hidden@127.0.0.1:1/missing",
        llm_active_model="fake",
    )
    unavailable_result = diagnose(unreachable)
    assert unavailable_result["database"]["reachable"] is False
    assert "hidden" not in json.dumps(unavailable_result)


def test_request_logs_have_correlation_without_private_content(database, caplog):
    cfg, _ = database
    private = "private-message-must-not-appear"
    with caplog.at_level(logging.INFO, logger="afterstory.http"):
        with TestClient(create_app(cfg)) as client:
            response = client.post(
                "/api/sessions/open",
                headers={"X-Request-ID": "test-request-42"},
                json={"version_id": "test-lan-v1"},
            )
            conversation_id = response.json()["conversation_id"]
            assert response.headers["X-Request-ID"] == "test-request-42"
            sent = client.post(
                f"/api/conversations/{conversation_id}/messages",
                headers={"X-Request-ID": "invalid request id"},
                json={"request_id": "request", "text": private},
            )
            assert sent.status_code == 200
            assert sent.headers["X-Request-ID"] != "invalid request id"
            assert len(sent.headers["X-Request-ID"]) == 36
            failed = client.post(
                "/api/instances",
                headers={"X-Request-ID": "domain-error-1"},
                json={"version_id": private},
            )
            assert failed.status_code == 404

        class FailedProvider:
            def generate(self, messages):
                raise ProviderError("llm_http_error")

        with TestClient(create_app(cfg, FailedProvider())) as client:
            opened = client.post(
                "/api/sessions/open", json={"version_id": "test-lan-v1"}
            ).json()
            failed_reply = client.post(
                f"/api/conversations/{opened['conversation_id']}/messages",
                headers={"X-Request-ID": "provider-error-1"},
                json={"request_id": "provider-error", "text": private + "-provider"},
            )
            assert failed_reply.status_code == 502

    records = [
        record.getMessage()
        for record in caplog.records
        if record.name == "afterstory.http"
    ]
    text = "\n".join(records)
    assert "test-request-42" in text
    assert "domain-error-1" in text
    assert "character_version_not_found" in text
    assert "llm_http_error" in text
    assert "provider-error-1" in text
    assert "/conversations/{conversation_id}/messages" in text
    assert private not in text
    assert conversation_id not in text
