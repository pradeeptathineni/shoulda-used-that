"""Thin read-only adapter over the installed official GitHub CLI."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shoulda_used_that.errors import (
    GitHubAuthError,
    GitHubError,
    GitHubPartialError,
    GitHubRateLimitError,
    GitHubSchemaError,
)

API_VERSION = "2022-11-28"
DEFAULT_ACCEPT = "application/vnd.github+json"
STAR_ACCEPT = "application/vnd.github.star+json"
TOKEN_PATTERN = re.compile(r"(?i)(gh[pousr]_[A-Za-z0-9_]+|bearer\s+\S+|token:\s*\S+)")


@dataclass(frozen=True, slots=True)
class GhResult:
    payload: Any
    tool_version: str
    endpoint: str
    paginated: bool


class GhClient:
    """Invoke `gh` with argument vectors, timeouts, and typed failures."""

    def __init__(self, *, timeout_seconds: float = 30.0, cwd: Path | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.cwd = cwd
        self._tool_version: str | None = None

    def check_environment(self) -> str:
        version = self._run(("gh", "--version"), operation="version")
        first_line = version.stdout.splitlines()[0] if version.stdout else ""
        if not first_line.startswith("gh version "):
            raise GitHubSchemaError(
                code="github_version_unrecognized",
                message="The installed gh CLI returned an unrecognized version response.",
            )
        auth = self._run(
            ("gh", "auth", "status", "--active", "--hostname", "github.com"),
            operation="auth",
        )
        if auth.returncode != 0:
            raise GitHubAuthError(
                code="github_auth_inactive",
                message=(
                    "GitHub CLI is not actively authenticated for github.com; run 'gh auth login'."
                ),
            )
        self._tool_version = first_line.removeprefix("gh version ").split()[0]
        return self._tool_version

    def repository(self, repository: str) -> GhResult:
        return self._api_json(f"repos/{repository}")

    def starred(self) -> GhResult:
        result = self._api_json("user/starred", accept=STAR_ACCEPT, paginate=True)
        pages = _require_list(result.payload, "starred repository pages")
        flattened: list[Any] = []
        for page in pages:
            flattened.extend(_require_list(page, "starred repository page"))
        return GhResult(flattened, result.tool_version, result.endpoint, paginated=True)

    def search(self, query: str, *, maximum: int = 100) -> GhResult:
        if maximum < 1 or maximum > 100:
            raise ValueError("bounded GitHub search maximum must be from 1 to 100")
        result = self._api_json(
            "search/repositories",
            fields={"q": query, "per_page": str(maximum), "page": "1"},
        )
        payload = _require_dict(result.payload, "repository search response")
        items = _require_list(payload.get("items"), "repository search items")
        return GhResult(items[:maximum], result.tool_version, result.endpoint, paginated=False)

    def _api_json(
        self,
        endpoint: str,
        *,
        accept: str = DEFAULT_ACCEPT,
        paginate: bool = False,
        fields: dict[str, str] | None = None,
        etag: str | None = None,
    ) -> GhResult:
        tool_version = self._tool_version or self.check_environment()
        args = [
            "gh",
            "api",
            "--method",
            "GET",
            "--header",
            f"Accept: {accept}",
            "--header",
            f"X-GitHub-Api-Version: {API_VERSION}",
        ]
        if etag:
            args.extend(("--header", f"If-None-Match: {etag}"))
        if paginate:
            args.extend(("--paginate", "--slurp"))
        args.append(endpoint)
        for key, value in sorted((fields or {}).items()):
            args.extend(("--field", f"{key}={value}"))
        completed = self._run(tuple(args), operation=f"api:{endpoint}")
        if completed.returncode != 0:
            self._raise_api_failure(endpoint, completed)
        if etag and not completed.stdout.strip():
            return GhResult({"not_modified": True}, tool_version, endpoint, paginate)
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            error_type = GitHubPartialError if paginate else GitHubSchemaError
            raise error_type(
                code="github_invalid_json",
                message=(
                    f"GitHub returned incomplete or invalid JSON for {endpoint}; "
                    "no partial result was accepted."
                ),
                details={"endpoint": endpoint},
            ) from exc
        return GhResult(payload, tool_version, endpoint, paginate)

    def _run(self, args: tuple[str, ...], *, operation: str) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(  # noqa: S603 - fixed executable and argument vector by design
                args,
                cwd=self.cwd,
                env=_minimal_environment(),
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise GitHubAuthError(
                code="github_cli_missing",
                message="The official gh CLI is required for live GitHub reads but was not found.",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise GitHubError(
                code="github_timeout",
                message=(
                    f"GitHub operation '{operation}' exceeded {self.timeout_seconds:g} seconds."
                ),
                details={"operation": operation},
            ) from exc

    def _raise_api_failure(
        self, endpoint: str, completed: subprocess.CompletedProcess[str]
    ) -> None:
        stderr = _redact(completed.stderr)
        lowered = stderr.casefold()
        details = {"endpoint": endpoint, "exit_code": completed.returncode}
        if "rate limit" in lowered or "http 429" in lowered:
            raise GitHubRateLimitError(
                code="github_rate_limited",
                message=f"GitHub rate-limited the read for {endpoint}.",
                details=details,
            )
        if "http 401" in lowered or "bad credentials" in lowered or "authentication" in lowered:
            raise GitHubAuthError(
                code="github_auth_failed",
                message=f"GitHub authentication failed while reading {endpoint}.",
                details=details,
            )
        raise GitHubError(
            code="github_transport_failed",
            message=f"GitHub read failed for {endpoint}: {stderr.strip() or 'no diagnostic'}",
            details=details,
        )


def _minimal_environment() -> dict[str, str]:
    allowed = (
        "PATH",
        "HOME",
        "GH_CONFIG_DIR",
        "XDG_CONFIG_HOME",
        "LANG",
        "LC_ALL",
        "NO_COLOR",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
    )
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    environment["GH_HOST"] = "github.com"
    environment["NO_COLOR"] = "1"
    return environment


def _redact(value: str) -> str:
    return TOKEN_PATTERN.sub("[REDACTED]", value)


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise GitHubSchemaError(
            code="github_schema_mismatch",
            message=f"GitHub {label} was not a JSON array.",
        )
    return value


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GitHubSchemaError(
            code="github_schema_mismatch",
            message=f"GitHub {label} was not a JSON object.",
        )
    return value
