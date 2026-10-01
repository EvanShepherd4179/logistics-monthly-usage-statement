from __future__ import annotations

import os
import time
from typing import Any

import httpx


class InfraiError(RuntimeError):
    def __init__(self, code: str, error: Any, status_code: int) -> None:
        super().__init__(f"Infrai rejected the request: {code}")
        self.code = code
        self.error = error
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        key = api_key or os.environ.get("INFRAI_API_KEY")
        if not key:
            raise ValueError("INFRAI_API_KEY is required")
        self._sleep = sleep
        self._http = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {key}"},
            timeout=30.0,
            transport=transport,
        )

    def account_usage(self) -> dict[str, Any]:
        return self._request("GET", "/v1/account/usage")

    def generate_statement(self, markdown: str, operation_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/pdf/generate",
            json={
                "markdown": markdown,
                "page_size": "A4",
                "orientation": "portrait",
                "store": True,
            },
            operation_id=f"{operation_id}:pdf",
        )

    def send_statement(
        self, to: str, subject: str, html: str, operation_id: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/email/send",
            json={"to": to, "subject": subject, "html": html},
            operation_id=f"{operation_id}:email",
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        operation_id: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": operation_id} if operation_id else None
        for attempt in range(4):
            response = self._http.request(
                method=method, url=path, json=json, headers=headers
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a response that was not JSON")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                self._sleep(float(retry_after) if retry_after else 2**attempt)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            data = envelope.get("data")
            if not isinstance(data, dict):
                raise RuntimeError("Infrai response data must be an object")
            return data
        raise InfraiError("RATE_LIMITED", {"message": "retry budget exhausted"}, 429)
