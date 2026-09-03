from __future__ import annotations

import json

import pytest

from archimedes_v0.v1_gemini_backend import (
    GEMINI_API_REVISION,
    GEMINI_INTERACTIONS_ENDPOINT,
    GEMINI_MODEL_ID,
    GEMINI_SEED,
    GEMINI_THINKING_LEVEL,
    GEMINI_THINKING_SUMMARIES,
    GEMINI_TIMEOUT_SECONDS,
    GeminiInteractionsBackend,
    InMemoryUsageSink,
    V1ProviderError,
)


class FakeTransport:
    def __init__(self, response, *, status=200):
        self.response = response
        self.status = status
        self.calls = []

    def post_json(self, *, url, headers, body, timeout_seconds):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "body": body,
                "timeout_seconds": timeout_seconds,
            }
        )
        encoded = self.response if isinstance(self.response, bytes) else json.dumps(self.response).encode()
        return self.status, encoded


def _response(structured=None, **overrides):
    structured = structured or {"candidates": []}
    response = {
        "id": "int-test-001",
        "model": GEMINI_MODEL_ID,
        "status": "completed",
        "steps": [
            {
                "type": "thought",
                "signature": "opaque-signature",
            },
            {
                "type": "model_output",
                "content": [{"type": "text", "text": json.dumps(structured, sort_keys=True)}],
            },
        ],
        "usage": {
            "total_input_tokens": 123,
            "total_output_tokens": 17,
            "total_thought_tokens": 88,
            "total_tokens": 228,
            "total_tool_use_tokens": 0,
        },
    }
    response.update(overrides)
    return response


def _invoke(transport, sink=None, payload=None):
    backend = GeminiInteractionsBackend(api_key="not-a-real-key", transport=transport, usage_sink=sink)
    return backend.invoke(
        role="critic",
        system_prompt="synthetic critic prompt",
        payload=payload or {"task": "select_A_interventions", "round_index": 2, "b": 1, "a": 2},
        response_schema={"type": "object", "properties": {"candidates": {"type": "array"}}},
        max_output_tokens=2048,
    )


def test_request_is_exactly_stateless_tool_free_and_frozen():
    transport = FakeTransport(_response())
    result = _invoke(transport)
    assert result == {"candidates": []}
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"] == GEMINI_INTERACTIONS_ENDPOINT
    assert call["timeout_seconds"] == GEMINI_TIMEOUT_SECONDS == 300.0
    assert call["headers"]["Api-Revision"] == GEMINI_API_REVISION == "2026-05-20"
    assert call["headers"]["x-goog-api-key"] == "not-a-real-key"

    body = json.loads(call["body"])
    assert body["model"] == GEMINI_MODEL_ID == "gemini-3.7-flash"
    assert body["stream"] is False
    assert body["store"] is False
    assert body["background"] is False
    assert "tools" not in body
    assert "previous_interaction_id" not in body
    assert body["generation_config"] == {
        "max_output_tokens": 2048,
        "seed": GEMINI_SEED,
        "thinking_level": GEMINI_THINKING_LEVEL,
        "thinking_summaries": GEMINI_THINKING_SUMMARIES,
        "tool_choice": "none",
    }
    assert body["generation_config"]["seed"] == 20260902
    assert body["generation_config"]["thinking_level"] == "high"
    assert body["generation_config"]["thinking_summaries"] == "none"
    assert body["response_format"]["type"] == "text"
    assert body["response_format"]["mime_type"] == "application/json"


def test_payload_canonicalization_is_insertion_order_invariant():
    t1, t2 = FakeTransport(_response()), FakeTransport(_response())
    _invoke(t1, payload={"task": "x", "round_index": 1, "z": {"b": 2, "a": 1}})
    _invoke(t2, payload={"z": {"a": 1, "b": 2}, "round_index": 1, "task": "x"})
    assert t1.calls[0]["body"] == t2.calls[0]["body"]


def test_usage_record_logs_provider_compute_without_reasoning_content():
    sink = InMemoryUsageSink()
    _invoke(FakeTransport(_response()), sink=sink)
    assert len(sink.records) == 1
    record = sink.records[0]
    assert record.interaction_id == "int-test-001"
    assert record.returned_model == GEMINI_MODEL_ID
    assert record.role == "critic"
    assert record.task == "select_A_interventions"
    assert record.round_index == 2
    assert record.total_input_tokens == 123
    assert record.total_output_tokens == 17
    assert record.total_thought_tokens == 88
    assert record.total_tokens == 228
    assert record.total_tool_use_tokens == 0
    assert len(record.request_sha256) == 64
    assert len(record.response_text_sha256) == 64
    assert not hasattr(record, "thought_text")


def test_http_failure_is_single_attempt_and_never_retried():
    transport = FakeTransport({"error": {"message": "busy"}}, status=503)
    with pytest.raises(V1ProviderError, match="HTTP status 503"):
        _invoke(transport)
    assert len(transport.calls) == 1


def test_wrong_model_id_aborts_instead_of_silently_accepting_revision():
    transport = FakeTransport(_response(model="gemini-3.7-flash-revised"))
    with pytest.raises(V1ProviderError, match="unexpected model identifier"):
        _invoke(transport)
    assert len(transport.calls) == 1


def test_noncompleted_status_aborts_without_followup_poll_or_retry():
    transport = FakeTransport(_response(status="in_progress"))
    with pytest.raises(V1ProviderError, match="not completed"):
        _invoke(transport)
    assert len(transport.calls) == 1


def test_unexpected_tool_or_function_step_is_rejected():
    response = _response()
    response["steps"].insert(1, {"type": "function_call", "name": "forbidden"})
    transport = FakeTransport(response)
    with pytest.raises(V1ProviderError, match="unexpected Gemini step type"):
        _invoke(transport)
    assert len(transport.calls) == 1


def test_invalid_structured_json_is_provider_protocol_failure():
    response = _response()
    response["steps"][-1]["content"][0]["text"] = "not-json"
    transport = FakeTransport(response)
    with pytest.raises(V1ProviderError, match="not valid JSON"):
        _invoke(transport)
    assert len(transport.calls) == 1


def test_api_key_is_never_embedded_in_request_body():
    transport = FakeTransport(_response())
    _invoke(transport)
    body = transport.calls[0]["body"]
    assert b"not-a-real-key" not in body
