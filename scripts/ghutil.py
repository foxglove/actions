"""GitHub REST and GraphQL client.

Uses FOX_FINE_GRAINED_TOKEN only. Never logs the token or Authorization header.
"""

from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import tempfile
import time

API = "https://api.github.com"
# curl --max-time is the first limit. On this host a stuck poll has ignored
# both that and SIGALRM, so the parent also SIGKILLs the curl process group.
_CURL_MAX_TIME = 45
_CURL_CONNECT_TIMEOUT = 15
_CURL_KILL_AFTER = 10


def _parse_curl_headers(raw: bytes) -> dict:
    """Headers from the last response. --location appends every hop to one file."""
    text = raw.decode("iso-8859-1", "replace")
    blocks = [block for block in text.split("\r\n\r\n") if block.strip()]
    if not blocks:
        return {}
    headers: dict[str, str] = {}
    for line in blocks[-1].splitlines()[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


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

    def _run_curl(self, cmd: list[str]) -> subprocess.CompletedProcess:
        """Run curl. SIGKILL the process group if it is still alive after the limit."""
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=_CURL_MAX_TIME + _CURL_KILL_AFTER)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()
            raise TimeoutError(f"GitHub request exceeded {_CURL_MAX_TIME}s")
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)

    def _curl(
        self, method: str, url: str, data: bytes | None, extra: dict
    ) -> tuple[int, dict, bytes]:
        """One GitHub call. The token stays in a mode-600 curl config, never on argv."""
        cfg_dir = tempfile.mkdtemp(prefix="ghcurl-")
        try:
            cfg_path = os.path.join(cfg_dir, "curl.cfg")
            body_path = os.path.join(cfg_dir, "body")
            hdr_path = os.path.join(cfg_dir, "headers")
            out_path = os.path.join(cfg_dir, "out")
            lines = ["silent", "show-error"]
            for key, value in self._headers(extra).items():
                safe = str(value).replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'header = "{key}: {safe}"')
            fd = os.open(cfg_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write("\n".join(lines) + "\n")
            if data is not None:
                with open(body_path, "wb") as fh:
                    fh.write(data)
            cmd = [
                "curl",
                "--config",
                cfg_path,
                "--max-time",
                str(_CURL_MAX_TIME),
                "--connect-timeout",
                str(_CURL_CONNECT_TIMEOUT),
                "--request",
                method,
                "--dump-header",
                hdr_path,
                "--output",
                out_path,
                "--location",
                "--max-redirs",
                "5",
                "--write-out",
                "%{http_code}",
                url,
            ]
            if data is not None:
                cmd[1:1] = ["--data-binary", f"@{body_path}"]
            proc = self._run_curl(cmd)
            if proc.returncode in (28, 124) or proc.returncode < 0:
                raise TimeoutError(f"GitHub request exceeded {_CURL_MAX_TIME}s")
            if proc.returncode != 0:
                err = proc.stderr.decode("utf-8", "replace")[:300]
                if self._token and self._token in err:
                    err = err.replace(self._token, "[redacted]")
                raise ConnectionError(f"curl exit {proc.returncode}: {err}")
            status_text = proc.stdout.decode("ascii", "replace").strip() or "0"
            status = int(status_text)
            raw = open(out_path, "rb").read() if os.path.exists(out_path) else b""
            hdr_raw = open(hdr_path, "rb").read() if os.path.exists(hdr_path) else b""
            return status, _parse_curl_headers(hdr_raw), raw
        finally:
            shutil.rmtree(cfg_dir, ignore_errors=True)

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
            try:
                status, headers, raw = self._curl(method, url, data, extra)
            except (TimeoutError, ConnectionError) as exc:
                last_err = exc
                print(f"transient read error; retrying ({attempt + 1}/{retries})", flush=True)
                time.sleep(min(30, 2 ** attempt))
                continue
            self._note_rest_limit(headers)
            if status >= 400:
                err_body = raw.decode("utf-8", "replace")
                last_err = GitHubError(
                    f"HTTP {status} {method} {url.split('?')[0]}", status, err_body[:500]
                )
                if status in (403, 429) and "secondary" in err_body.lower():
                    retry_after = headers.get("retry-after")
                    delay = int(retry_after) if retry_after and str(retry_after).isdigit() else min(120, 10 * (attempt + 1))
                    print(f"secondary rate limit; sleeping {delay}s", flush=True)
                    time.sleep(delay)
                    continue
                if status in (403, 429) and self._is_rate_limit(status, err_body, headers):
                    retry_after = headers.get("retry-after")
                    if retry_after and str(retry_after).isdigit():
                        reset = int(time.time()) + int(retry_after)
                    else:
                        reset = int(headers.get("x-ratelimit-reset") or time.time() + 60)
                    self._sleep_until(reset, "core")
                    continue
                if status in (500, 502, 503, 504):
                    time.sleep(min(60, 2 ** attempt))
                    continue
                raise last_err
            if not raw:
                return {}, headers
            return json.loads(raw.decode()), headers
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
        if "secondary rate" in text:
            return False
        return "rate limit" in text

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
