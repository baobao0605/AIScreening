"""Anthropic Messages API provider."""

from __future__ import annotations

import json
import random
import time
from urllib import error, request


class AnthropicProviderError(RuntimeError):
    """Raised when Anthropic provider requests fail."""


def _is_retryable_http_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599


def _is_non_retryable_quota_error(message: str) -> bool:
    lowered = message.casefold()
    non_retryable_fragments = (
        "prepayment credits are depleted",
        "credits are depleted",
        "insufficient balance",
        "quota exceeded",
        "billing",
    )
    return any(fragment in lowered for fragment in non_retryable_fragments)


def _is_retryable_transport_error(message: str) -> bool:
    lowered = message.casefold()
    retryable_fragments = (
        "incompleteread",
        "connection reset",
        "connection aborted",
        "unexpected eof",
        "timed out",
        "timeout",
        "temporarily unavailable",
        "temporary failure",
    )
    return any(fragment in lowered for fragment in retryable_fragments)


class AnthropicProvider:
    """Provider that calls Anthropic Messages API and returns text content."""

    provider_name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None,
        model_name: str,
        base_url: str,
        timeout_seconds: float,
        max_tokens: int,
        request_max_retries: int,
        request_retry_delay_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.request_max_retries = max(1, request_max_retries)
        self.request_retry_delay_seconds = max(0.0, request_retry_delay_seconds)

    def _messages_endpoint(self) -> str:
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/messages"
        return f"{self.base_url}/v1/messages"

    def screen(self, prompt: str) -> str:
        if not self.api_key:
            raise AnthropicProviderError("Missing ANTHROPIC_API_KEY.")
        if not self.model_name:
            raise AnthropicProviderError("Missing anthropic.model in settings.")
        if not self.base_url:
            raise AnthropicProviderError("Missing anthropic.base_url in settings.")

        payload = {
            "model": self.model_name,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        req = request.Request(
            self._messages_endpoint(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )

        parsed: dict[str, object] | None = None
        last_error: Exception | None = None
        quota_depleted = False
        for attempt in range(1, self.request_max_retries + 1):
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
                last_error = None
                break
            except error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="ignore")
                if _is_non_retryable_quota_error(body):
                    quota_depleted = True
                last_error = AnthropicProviderError(
                    f"Anthropic request failed with HTTP {exc.code}: {body}"
                )
                if quota_depleted or not _is_retryable_http_status(exc.code) or attempt >= self.request_max_retries:
                    break
                if self.request_retry_delay_seconds > 0:
                    base_delay = self.request_retry_delay_seconds * (2 ** (attempt - 1))
                    jittered_delay = base_delay * random.uniform(0.7, 1.8)
                    time.sleep(jittered_delay)
            except error.URLError as exc:
                last_error = AnthropicProviderError(f"Anthropic request failed: {exc}")
                if attempt >= self.request_max_retries:
                    break
                if self.request_retry_delay_seconds > 0:
                    base_delay = self.request_retry_delay_seconds * (2 ** (attempt - 1))
                    jittered_delay = base_delay * random.uniform(0.7, 1.8)
                    time.sleep(jittered_delay)
            except Exception as exc:
                last_error = AnthropicProviderError(f"Anthropic request failed: {exc}")
                if not _is_retryable_transport_error(str(exc)) or attempt >= self.request_max_retries:
                    break
                if self.request_retry_delay_seconds > 0:
                    base_delay = self.request_retry_delay_seconds * (2 ** (attempt - 1))
                    jittered_delay = base_delay * random.uniform(0.7, 1.8)
                    time.sleep(jittered_delay)

        if last_error is not None:
            if quota_depleted:
                raise AnthropicProviderError(
                    "Provider billing credits appear depleted. Please top up billing and retry."
                ) from last_error
            raise last_error
        if not isinstance(parsed, dict):
            raise AnthropicProviderError("Anthropic response was not a JSON object.")

        content = parsed.get("content")
        if not isinstance(content, list):
            raise AnthropicProviderError("Anthropic response missing content blocks.")

        text_parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())

        if not text_parts:
            raise AnthropicProviderError("Anthropic response had no text content blocks.")
        return "\n".join(text_parts).strip()
