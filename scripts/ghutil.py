"""GitHub REST and GraphQL client.

Uses FOX_FINE_GRAINED_TOKEN only. Never logs the token or Authorization header.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

API = "https://api.github.com"


class GitHubError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


class GitHub:
    def __init__(self) -> None:
        token = os.environ.get("FOX_FINE_GRAINED_TOKEN")
        if not token:
            raise SystemExit("FOX_FINE_GRAINED_TOKEN is not set")
        self._token = token
        self.core_remaining = 5000
        self.graphql_remaining = 5000
        self.core_reset = 0
        self.graphql_reset = 0

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "foxglove-pr-review-study",
        }
        if extra:
            headers.update(extra)
        return headers

    def _sleep_until(self, reset_epoch: int, reason: str) -> None:
        wait = max(0, reset_epoch - int(time.time())) + 2
        wait = min(wait, 3700)
        print(f"rate limit ({reason}); sleeping {wait}s", flush=True)
        time.sleep(wait)

    def request(
        self,
        method: str,
        url: str,
        body: dict | None = None,
        accept: str | None = None,
        retries: int = 6,
    ) -> tuple[dict | list, dict]:
        if url.startswith("/"):
            url = API + url
        data = None if body is None else json.dumps(body).encode()
        extra = {"Content-Type": "application/json"} if body is not None else {}
        if accept:
            extra["Accept"] = accept
        last_err: Exception | None = None
        for attempt in range(retries):
            if self.core_remaining < 5 and self.core_reset:
                self._sleep_until(self.core_reset, "core")
            req = urllib.request.Request(url, data=data, headers=self._headers(extra), method=method)
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    raw = resp.read()
                    headers = {k.lower(): v for k, v in resp.headers.items()}
                    self._note_rest_limit(headers)
                    if not raw:
                        return {}, headers
                    return json.loads(raw.decode()), headers
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", "replace")
                headers = {k.lower(): v for k, v in exc.headers.items()}
                self._note_rest_limit(headers)
                last_err = GitHubError(f"HTTP {exc.code} {method} {url.split('?')[0]}", exc.code, err_body[:500])
                if exc.code in (403, 429) and self._is_rate_limit(exc.code, err_body, headers):
                    reset = int(headers.get("x-ratelimit-reset") or time.time() + 60)
                    self._sleep_until(reset, "core")
                    continue
                if exc.code in (500, 502, 503, 504):
                    time.sleep(min(60, 2 ** attempt))
                    continue
                if exc.code == 403 and "secondary" in err_body.lower():
                    time.sleep(min(120, 10 * (attempt + 1)))
                    continue
                raise last_err from exc
            except urllib.error.URLError as exc:
                last_err = exc
                time.sleep(min(30, 2 ** attempt))
        raise GitHubError(f"request failed after retries: {last_err}")

    def _note_rest_limit(self, headers: dict) -> None:
        if "x-ratelimit-remaining" in headers and headers.get("x-ratelimit-resource") in (None, "core"):
            try:
                self.core_remaining = int(headers["x-ratelimit-remaining"])
                self.core_reset = int(headers.get("x-ratelimit-reset") or 0)
            except ValueError:
                pass

    @staticmethod
    def _is_rate_limit(status: int, body: str, headers: dict) -> bool:
        if headers.get("x-ratelimit-remaining") == "0":
            return True
        text = body.lower()
        return "rate limit" in text or "secondary rate" in text

    def graphql(self, query: str, variables: dict | None = None, retries: int = 6) -> dict:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        last_err: Exception | None = None
        for attempt in range(retries):
            if self.graphql_remaining < 50 and self.graphql_reset:
                self._sleep_until(self.graphql_reset, "graphql")
            try:
                data, _headers = self.request("POST", "/graphql", payload)
            except GitHubError as exc:
                last_err = exc
                if exc.status in (502, 503, 504) or (exc.status == 403):
                    time.sleep(min(60, 2 ** attempt))
                    continue
                raise
            if "errors" in data and not data.get("data"):
                msg = json.dumps(data["errors"])[:800]
                if "rate limit" in msg.lower() or "something went wrong" in msg.lower():
                    time.sleep(min(60, 2 ** attempt))
                    last_err = GitHubError(msg)
                    continue
                raise GitHubError(f"graphql error: {msg}")
            limit = (data.get("data") or {}).get("rateLimit") or {}
            if "remaining" in limit:
                self.graphql_remaining = int(limit["remaining"])
                # resetAt is ISO8601
                reset_at = limit.get("resetAt")
                if reset_at:
                    from datetime import datetime

                    self.graphql_reset = int(datetime.fromisoformat(reset_at.replace("Z", "+00:00")).timestamp())
            # Partial FORBIDDEN errors are returned with data. Caller decides.
            return data
        raise GitHubError(f"graphql failed after retries: {last_err}")
