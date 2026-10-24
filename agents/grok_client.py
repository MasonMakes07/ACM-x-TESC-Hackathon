"""Minimal Grok (xAI) chat-completions client with timeouts and retries.

Owner: Person 2 (Grok Agent Intelligence). Talks directly to the xAI Grok REST
API with requests. Credentials come only from .env via config.py.
"""

import os
import time

import requests

import config
from agents.agent_errors import GrokError

DEFAULT_BASE_URL = "https://api.x.ai/v1"
RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
ERROR_BODY_PREVIEW_CHARS = 200


# =============================================================================
# GrokClient
# =============================================================================

# Sends chat-completion requests to Grok and returns the assistant message.
class GrokClient:
    # Stores credentials and request settings; reads .env for omitted values.
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        retry_delay_seconds: float = 1.0,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key or config.get_required_env("XAI_API_KEY")
        self.model = model or config.get_required_env("XAI_MODEL")
        root_url = base_url or os.getenv("XAI_BASE_URL") or DEFAULT_BASE_URL
        self.endpoint = root_url.rstrip("/") + "/chat/completions"
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.session = session or requests.Session()

    # Sends messages (and optional tool definitions) and returns the reply message.
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload: dict = {"model": self.model, "messages": messages, "temperature": 0.2}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        for attempt in range(self.max_retries + 1):
            is_last_attempt = attempt == self.max_retries
            try:
                response = self.session.post(
                    self.endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as error:
                if is_last_attempt:
                    raise GrokError("Could not reach the Grok API.") from error
                self._wait(attempt)
                continue
            if response.status_code in RETRYABLE_STATUS_CODES and not is_last_attempt:
                self._wait(attempt)
                continue
            if response.status_code != 200:
                preview = response.text[:ERROR_BODY_PREVIEW_CHARS]
                raise GrokError(
                    f"Grok API returned HTTP {response.status_code}: {preview}"
                )
            return self._extract_message(response)
        raise GrokError("Grok API retries exhausted.")

    # Sleeps with exponential backoff before the next retry.
    def _wait(self, attempt: int) -> None:
        time.sleep(self.retry_delay_seconds * (2**attempt))

    # Pulls the first choice's message out of a response, validating its shape.
    @staticmethod
    def _extract_message(response: requests.Response) -> dict:
        try:
            message = response.json()["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise GrokError("Grok API returned an unexpected response.") from error
        if not isinstance(message, dict):
            raise GrokError("Grok API returned an unexpected message format.")
        return message
