#!/usr/bin/env python3
"""Mint a GitHub App installation token for one permission set.

Prints the token on stdout. Errors go to stderr. The workflow uses this for
the actions: write token that re-runs an earlier pull_request review check.
That mint happens only after an LGTM verdict, including when local beefcake
posted the review and the review-token mint did not run.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


def load_permissions(text: str) -> dict[str, str]:
    """Return permission name to access level from a JSON object."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise SystemExit(f"TOKEN_PERMISSIONS is not JSON. {error}") from error
    if not isinstance(value, dict) or not value:
        raise SystemExit(
            "TOKEN_PERMISSIONS must be a JSON object of permission names to access levels."
        )
    permissions: dict[str, str] = {}
    for key, level in value.items():
        if not isinstance(key, str) or not isinstance(level, str) or not key or not level:
            raise SystemExit(
                "TOKEN_PERMISSIONS must be a JSON object of permission names to access levels."
            )
        permissions[key] = level
    return permissions


def mint_installation_token(
    app_id: str,
    private_key: str,
    repository: str,
    permissions: dict[str, str],
) -> str:
    """Return an installation token for this repository and permission set."""
    if not app_id or not private_key.strip():
        raise SystemExit(
            "Refreshing the review check needs secrets BEEFCAKE_APP_ID and "
            "BEEFCAKE_APP_PRIVATE_KEY."
        )
    if not app_id.isdigit():
        raise SystemExit("BEEFCAKE_APP_ID must be the numeric GitHub App id.")
    if not repository or "/" not in repository:
        raise SystemExit("GITHUB_REPOSITORY must be owner/name.")

    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    now = int(time.time())
    payload = b64(
        json.dumps(
            {"iat": now - 60, "exp": now + 540, "iss": app_id},
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode()
    key_file = tempfile.NamedTemporaryFile("w", delete=False)
    try:
        key_file.write(private_key if private_key.endswith("\n") else private_key + "\n")
        key_file.close()
        os.chmod(key_file.name, 0o600)
        signature = subprocess.check_output(
            ["openssl", "dgst", "-sha256", "-sign", key_file.name],
            input=signing_input,
        )
    except subprocess.CalledProcessError as error:
        raise SystemExit(
            "Could not sign the GitHub App JWT. Check that BEEFCAKE_APP_PRIVATE_KEY is a PEM private key."
        ) from error
    finally:
        try:
            os.remove(key_file.name)
        except OSError:
            pass

    jwt = f"{header}.{payload}.{b64(signature)}"
    print(f"::add-mask::{jwt}", file=sys.stderr)

    def github_json(
        method: str,
        url: str,
        body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
                "User-Agent": "foxglove-actions-review",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                loaded = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:500]
            raise SystemExit(
                f"GitHub {method} {url.split('?')[0]} failed: {error.code} {detail}"
            ) from error
        if not isinstance(loaded, dict):
            raise SystemExit(f"GitHub {method} {url.split('?')[0]} did not return an object.")
        return loaded

    installation = github_json("GET", f"https://api.github.com/repos/{repository}/installation")
    installation_id = installation.get("id")
    if not isinstance(installation_id, int):
        raise SystemExit("GitHub did not return an installation id for this repository.")
    token_payload = github_json(
        "POST",
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        {"permissions": permissions},
    )
    token = token_payload.get("token")
    if not isinstance(token, str) or not token:
        raise SystemExit("GitHub did not return an installation token.")
    print(f"::add-mask::{token}", file=sys.stderr)
    return token


def main() -> int:
    app_id = os.environ.get("APP_ID", "").strip()
    private_key = os.environ.get("APP_PRIVATE_KEY", "")
    if "\n" not in private_key and "\\n" in private_key:
        private_key = private_key.replace("\\n", "\n")
    try:
        permissions = load_permissions(os.environ.get("TOKEN_PERMISSIONS", ""))
        token = mint_installation_token(
            app_id,
            private_key,
            os.environ.get("GITHUB_REPOSITORY", ""),
            permissions,
        )
    except SystemExit as error:
        message = error.code if isinstance(error.code, str) else "Could not mint an installation token."
        print(message, file=sys.stderr)
        return 1
    print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
