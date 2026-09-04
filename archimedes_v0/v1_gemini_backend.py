from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Protocol


GEMINI_INTERACTIONS_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_API_REVISION = "2026-05-20"
GEMINI_MODEL_ID = "gemini-3.7-flash"
GEMINI_THINKING_LEVEL = "high"
GEMINI_THINKING_SUMMARIES = "none"
GEMINI_SEED = 20260902
GEMINI_TIMEOUT_SECONDS = 300.0


class V1ProviderError(RuntimeError):
    """Infrastructure/provider failure that must abort scientific execution.

    This exception is intentionally distinct from semantic model-output failures.
    The V1 adapter performs no automatic retries. A provider failure therefore
    cannot silently consume duplicate inference compute or become arm-dependent.
    """


@dataclass(frozen=True)
class GeminiUsageRecord:
    interaction_id: str | None
    returned_model: str
    status: str
    role: str
    task: str | None
    round_index: int | None
    max_output_tokens: int
    request_sha256: str
    response_text_sha256: str
    total_input_tokens: int | None
    total_output_tokens: int | None
    total_thought_tokens: int | None
    total_tokens: int | None
    total_tool_use_tokens: int | None


class UsageSink(Protocol):
    def append(self, record: GeminiUsageRecord) -> None:
        ...


class InMemoryUsageSink:
    def __init__(self):
        self.records: list[GeminiUsageRecord] = []

    def append(self, record: GeminiUsageRecord) -> None:
        self.records.append(record)


class HTTPTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        ...


class UrllibHTTPTransport:
    """Single-attempt standard-library transport. No implicit retry layer."""

    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        request = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return int(response.status), response.read()
        except urllib.error.HTTPError as exc:
            return int(exc.code), exc.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise V1ProviderError(f"Gemini transport failure: {type(exc).__name__}") from exc


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_model_text(response: dict[str, Any]) -> str:
    steps = response.get("steps")
    if not isinstance(steps, list):
        raise V1ProviderError("Gemini completed response omitted steps array")

    text_parts: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            raise V1ProviderError("Gemini response contained malformed step")
        step_type = step.get("type")
        if step_type == "thought":
            continue
        if step_type != "model_output":
            raise V1ProviderError(f"unexpected Gemini step type: {step_type!r}")
        content = step.get("content")
        if not isinstance(content, list):
            raise V1ProviderError("Gemini model_output omitted content array")
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "text" or not isinstance(block.get("text"), str):
                raise V1ProviderError("Gemini structured-output response contained non-text model content")
            text_parts.append(block["text"])

    if not text_parts:
        raise V1ProviderError("Gemini completed response contained no model text")
    return "".join(text_parts)


def _optional_int(mapping: dict[str, Any], key: str) -> int | None:
    value = mapping.get(key)
    return value if type(value) is int else None


class GeminiInteractionsBackend:
    """Frozen direct-REST backend for Archimedes V1 pre-exposure testing.

    Scientific execution semantics:
      * one POST per model-call slot;
      * no automatic retry;
      * no persistent interaction / previous_interaction_id;
      * store=false, stream=false, background=false;
      * no tools and tool_choice=none;
      * high thinking, no thought summaries;
      * fixed seed and exact slot max-output cap;
      * static JSON-schema structured output;
      * missing/null interaction id permitted only for the frozen stateless
        store=false request;
      * any other infrastructure/protocol failure raises V1ProviderError and aborts
        the scientific run rather than becoming a score or receiving a retry.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: HTTPTransport | None = None,
        usage_sink: UsageSink | None = None,
        endpoint: str = GEMINI_INTERACTIONS_ENDPOINT,
        timeout_seconds: float = GEMINI_TIMEOUT_SECONDS,
        seed: int = GEMINI_SEED,
    ):
        resolved_key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
        if not resolved_key:
            raise V1ProviderError("GEMINI_API_KEY is required for Gemini provider execution")
        self._api_key = resolved_key
        self._transport = transport or UrllibHTTPTransport()
        self._usage_sink = usage_sink
        self._endpoint = endpoint
        self._timeout_seconds = float(timeout_seconds)
        self._seed = int(seed)

    def invoke(
        self,
        *,
        role: str,
        system_prompt: str,
        payload: dict[str, Any],
        response_schema: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        input_text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        request_body = {
            "model": GEMINI_MODEL_ID,
            "input": input_text,
            "system_instruction": system_prompt,
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": response_schema,
            },
            "stream": False,
            "store": False,
            "background": False,
            "generation_config": {
                "max_output_tokens": int(max_output_tokens),
                "seed": self._seed,
                "thinking_level": GEMINI_THINKING_LEVEL,
                "thinking_summaries": GEMINI_THINKING_SUMMARIES,
                "tool_choice": "none",
            },
        }
        body = _canonical_json_bytes(request_body)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-goog-api-key": self._api_key,
            "Api-Revision": GEMINI_API_REVISION,
        }

        status_code, raw_response = self._transport.post_json(
            url=self._endpoint,
            headers=headers,
            body=body,
            timeout_seconds=self._timeout_seconds,
        )
        if status_code < 200 or status_code >= 300:
            raise V1ProviderError(f"Gemini HTTP status {status_code}; no retry permitted")

        try:
            response = json.loads(raw_response.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise V1ProviderError("Gemini returned non-JSON response") from exc
        if not isinstance(response, dict):
            raise V1ProviderError("Gemini response root must be an object")
        if response.get("status") != "completed":
            raise V1ProviderError(f"Gemini interaction status is not completed: {response.get('status')!r}")
        if response.get("model") != GEMINI_MODEL_ID:
            raise V1ProviderError(
                f"Gemini returned unexpected model identifier {response.get('model')!r}; expected {GEMINI_MODEL_ID!r}"
            )

        output_text = _extract_model_text(response)
        try:
            structured = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise V1ProviderError("Gemini structured-output text is not valid JSON") from exc
        if not isinstance(structured, dict):
            raise V1ProviderError("Gemini structured output must be a JSON object")

        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        raw_interaction_id = response.get("id")
        if raw_interaction_id is None:
            if request_body["store"] is not False:
                raise V1ProviderError("Gemini completed response omitted interaction id for a stored interaction")
            interaction_id: str | None = None
        elif isinstance(raw_interaction_id, str) and raw_interaction_id:
            interaction_id = raw_interaction_id
        else:
            raise V1ProviderError("Gemini completed response contained invalid interaction id")

        record = GeminiUsageRecord(
            interaction_id=interaction_id,
            returned_model=response["model"],
            status=response["status"],
            role=role,
            task=payload.get("task") if isinstance(payload.get("task"), str) else None,
            round_index=payload.get("round_index") if type(payload.get("round_index")) is int else None,
            max_output_tokens=int(max_output_tokens),
            request_sha256=_sha256(body),
            response_text_sha256=_sha256(output_text.encode("utf-8")),
            total_input_tokens=_optional_int(usage, "total_input_tokens"),
            total_output_tokens=_optional_int(usage, "total_output_tokens"),
            total_thought_tokens=_optional_int(usage, "total_thought_tokens"),
            total_tokens=_optional_int(usage, "total_tokens"),
            total_tool_use_tokens=_optional_int(usage, "total_tool_use_tokens"),
        )
        if self._usage_sink is not None:
            self._usage_sink.append(record)
        return structured


def usage_records_json(records: list[GeminiUsageRecord]) -> str:
    """Canonical trusted-side serialization for compute auditing."""
    return json.dumps([asdict(record) for record in records], sort_keys=True, separators=(",", ":"))
