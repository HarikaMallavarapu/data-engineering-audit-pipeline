from app.copilot import provider
from app.core.config import Settings
from pydantic import SecretStr


def test_schema_inference_uses_local_fallback_without_a_provider_key():
    profile = {
        "columns": ["account_id", "email_address", "score"],
        "inferred_types": {"account_id": "string", "email_address": "string", "score": "decimal"},
        "null_counts": {"account_id": 0, "email_address": 1, "score": 0},
        "distinct_counts": {"account_id": 4, "email_address": 3, "score": 2},
        "row_count": 4,
    }
    analysis = provider.infer_schema(profile, Settings(ai_provider="none"))
    assert analysis["mode"] == "local"
    assert analysis["fallback_reason"] == "provider_key_not_configured"
    assert analysis["candidate_key_columns"] == ["account_id"]
    assert next(column for column in analysis["columns"] if column["name"] == "email_address")["pii_risk"]


def test_openrouter_receives_only_profile_metadata_and_returns_validated_suggestions(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"dataset_kind":"support tickets","summary":"Ticket records.","columns":[{"name":"ticket_id","semantic_type":"identifier","description":"Ticket key.","pii_risk":false},{"name":"invented","semantic_type":"bad","description":"Ignore.","pii_risk":false}],"candidate_key_columns":["ticket_id","invented"],"quality_notes":[]}'
                        }
                    }
                ]
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(provider.httpx, "post", fake_post)
    profile = {
        "columns": ["ticket_id", "summary"],
        "inferred_types": {"ticket_id": "integer", "summary": "string"},
        "null_counts": {"ticket_id": 0, "summary": 1},
        "distinct_counts": {"ticket_id": 10, "summary": 9},
        "value_shapes": {"summary": {"mixed_text": 5}},
        "row_count": 10,
        "sample_values": ["private row content must not be sent"],
    }
    settings = Settings(
        ai_provider="openrouter",
        openrouter_api_key=SecretStr("test-secret"),
        openrouter_model="test/model",
    )
    analysis = provider.infer_schema(profile, settings)
    request_body = captured["json"]
    sent_content = request_body["messages"][1]["content"]
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-secret"
    assert "private row content" not in sent_content
    assert "ticket_id" in sent_content
    assert analysis["mode"] == "llm"
    assert [column["name"] for column in analysis["columns"]] == ["ticket_id"]
    assert analysis["candidate_key_columns"] == ["ticket_id"]


def test_provider_failure_falls_back_without_failing_schema_processing(monkeypatch):
    def fail_request(*_args, **_kwargs):
        raise provider.httpx.ConnectError("offline")

    monkeypatch.setattr(provider.httpx, "post", fail_request)
    settings = Settings(
        ai_provider="gemini",
        gemini_api_key=SecretStr("test-secret"),
    )
    analysis = provider.infer_schema(
        {"columns": ["id"], "inferred_types": {"id": "integer"}, "row_count": 0},
        settings,
    )
    assert analysis["mode"] == "local"
    assert analysis["fallback_reason"] == "provider_unavailable"


def test_gemini_provider_uses_key_header_and_json_generation(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"dataset_kind":"inventory","summary":"Inventory rows.","columns":[{"name":"sku","semantic_type":"identifier","description":"Product key.","pii_risk":false}],"candidate_key_columns":["sku"],"quality_notes":[]}'
                                }
                            ]
                        }
                    }
                ]
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(provider.httpx, "post", fake_post)
    settings = Settings(
        ai_provider="gemini",
        gemini_api_key=SecretStr("test-gemini-secret"),
        gemini_model="test-gemini-model",
    )
    analysis = provider.infer_schema(
        {
            "columns": ["sku"],
            "inferred_types": {"sku": "string"},
            "null_counts": {"sku": 0},
            "distinct_counts": {"sku": 5},
            "row_count": 5,
        },
        settings,
    )

    assert captured["url"].endswith("/v1beta/models/test-gemini-model:generateContent")
    assert captured["headers"]["x-goog-api-key"] == "test-gemini-secret"
    assert captured["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert analysis["mode"] == "llm"
    assert analysis["provider"] == "gemini"
    assert analysis["candidate_key_columns"] == ["sku"]
