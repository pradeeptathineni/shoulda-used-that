"""Thin read-only adapter over the installed official GitHub CLI."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urlparse

from shoulda_used_that.errors import (
    GitHubAuthError,
    GitHubError,
    GitHubNotFoundError,
    GitHubPartialError,
    GitHubRateLimitError,
    GitHubSchemaError,
)
from shoulda_used_that.models import normalize_repository

API_VERSION = "2026-03-10"
DEFAULT_ACCEPT = "application/vnd.github+json"
STAR_ACCEPT = "application/vnd.github.star+json"
MAX_API_RESPONSE_BYTES = 20 * 1024 * 1024
MAX_SBOM_RESPONSE_BYTES = 10 * 1024 * 1024
TOKEN_PATTERN = re.compile(
    r"(?i)(github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9_]+|bearer\s+\S+|token:\s*\S+)"
)


@dataclass(frozen=True, slots=True)
class GhResult:
    payload: Any
    tool_version: str
    endpoint: str
    paginated: bool


@dataclass(frozen=True, slots=True)
class GhSbomResult:
    state: Literal["available", "pending"]
    payload: dict[str, Any] | None
    report_id: str
    tool_version: str


@dataclass(frozen=True, slots=True)
class GhAuthStatus:
    login: str
    host: str
    scopes: tuple[str, ...]
    token_source: str
    tool_version: str


class GhClient:
    """Invoke `gh` with argument vectors, timeouts, and typed failures."""

    def __init__(self, *, timeout_seconds: float = 30.0, cwd: Path | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.cwd = cwd
        self._tool_version: str | None = None

    def check_environment(self) -> str:
        tool_version = self._read_tool_version()
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
        return tool_version

    def auth_status(self) -> GhAuthStatus:
        """Read active identity and scopes without retrieving or printing the token."""

        tool_version = self._read_tool_version()
        completed = self._run(
            (
                "gh",
                "auth",
                "status",
                "--active",
                "--hostname",
                "github.com",
                "--json",
                "hosts",
            ),
            operation="auth-status-json",
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise GitHubSchemaError(
                code="github_auth_schema_invalid",
                message="GitHub CLI returned invalid JSON for active authentication state.",
            ) from exc
        hosts = payload.get("hosts") if isinstance(payload, dict) else None
        accounts = hosts.get("github.com") if isinstance(hosts, dict) else None
        if not isinstance(accounts, list):
            raise GitHubAuthError(
                code="github_auth_inactive",
                message="GitHub CLI has no active github.com account.",
            )
        active = [
            item for item in accounts if isinstance(item, dict) and item.get("active") is True
        ]
        if len(active) != 1 or active[0].get("state") != "success":
            raise GitHubAuthError(
                code="github_auth_inactive",
                message="GitHub CLI has no single successful active github.com account.",
            )
        account = active[0]
        login = account.get("login")
        host = account.get("host")
        scopes_value = account.get("scopes")
        token_source = account.get("tokenSource")
        if (
            not isinstance(login, str)
            or not isinstance(host, str)
            or not isinstance(token_source, str)
        ):
            raise GitHubSchemaError(
                code="github_auth_schema_invalid",
                message="GitHub CLI authentication JSON omitted identity fields.",
            )
        if isinstance(scopes_value, str):
            scopes = tuple(
                sorted(
                    {item.strip() for item in scopes_value.split(",") if item.strip()},
                    key=str.casefold,
                )
            )
        elif isinstance(scopes_value, list) and all(isinstance(item, str) for item in scopes_value):
            scopes = tuple(sorted(set(scopes_value), key=str.casefold))
        else:
            raise GitHubSchemaError(
                code="github_auth_schema_invalid",
                message="GitHub CLI authentication JSON omitted its scope list.",
            )
        return GhAuthStatus(login, host, scopes, token_source, tool_version)

    def repository(self, repository: str) -> GhResult:
        canonical = normalize_repository(repository)
        return self._api_json(f"repos/{canonical}")

    def repository_languages(self, repository: str) -> GhResult:
        canonical = normalize_repository(repository)
        return self._api_json(f"repos/{canonical}/languages")

    def repository_commit(self, repository: str, reference: str) -> GhResult:
        canonical = normalize_repository(repository)
        if not reference.strip():
            raise ValueError("repository commit reference cannot be empty")
        encoded_reference = quote(reference.strip(), safe="")
        return self._api_json(f"repos/{canonical}/commits/{encoded_reference}")

    def dependency_sbom(self, repository: str) -> GhSbomResult:
        """Start and fetch GitHub's current asynchronous dependency-graph report."""

        canonical = normalize_repository(repository)
        prefix = f"/repos/{canonical}/dependency-graph/sbom/fetch-report/"
        generated = self._api_json(f"repos/{canonical}/dependency-graph/sbom/generate-report")
        generated_payload = _require_dict(generated.payload, "SBOM report response")
        report_url = generated_payload.get("sbom_url")
        if not isinstance(report_url, str):
            raise GitHubSchemaError(
                code="github_sbom_schema_mismatch",
                message="GitHub's SBOM report response omitted sbom_url.",
            )
        parsed = urlparse(report_url)
        if parsed.scheme != "https" or parsed.netloc != "api.github.com":
            raise GitHubSchemaError(
                code="github_sbom_url_unsafe",
                message="GitHub returned an SBOM report URL outside api.github.com.",
            )
        if not parsed.path.casefold().startswith(prefix.casefold()):
            raise GitHubSchemaError(
                code="github_sbom_url_mismatch",
                message="GitHub returned an SBOM report URL for a different repository.",
            )
        report_id = parsed.path[len(prefix) :]
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", report_id):
            raise GitHubSchemaError(
                code="github_sbom_report_id_invalid",
                message="GitHub returned an invalid asynchronous SBOM report identifier.",
            )
        fetched = self._api_json(
            parsed.path.lstrip("/"), maximum_output_bytes=MAX_SBOM_RESPONSE_BYTES
        )
        payload = _require_dict(fetched.payload, "SBOM report document")
        if isinstance(payload.get("spdxVersion"), str):
            return GhSbomResult("available", payload, report_id, fetched.tool_version)
        message = payload.get("message")
        if isinstance(message, str) and any(
            marker in message.casefold() for marker in ("pending", "progress", "generating")
        ):
            return GhSbomResult("pending", None, report_id, fetched.tool_version)
        if isinstance(message, str) and "fail" in message.casefold():
            raise GitHubError(
                code="github_sbom_generation_failed",
                message="GitHub reported that dependency-graph SBOM generation failed.",
            )
        raise GitHubSchemaError(
            code="github_sbom_schema_mismatch",
            message="GitHub's completed SBOM report was not an SPDX document.",
        )

    def starred(self) -> GhResult:
        result = self._api_json("user/starred", accept=STAR_ACCEPT, paginate=True)
        pages = _require_list(result.payload, "starred repository pages")
        flattened: list[Any] = []
        for page in pages:
            flattened.extend(_require_list(page, "starred repository page"))
        return GhResult(flattened, result.tool_version, result.endpoint, paginated=True)

    def user_starred(self, login: str) -> GhResult:
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", login):
            raise ValueError("GitHub login is invalid")
        result = self._api_json(f"users/{login}/starred", paginate=True)
        pages = _require_list(result.payload, "public starred repository pages")
        flattened: list[Any] = []
        for page in pages:
            flattened.extend(_require_list(page, "public starred repository page"))
        return GhResult(flattened, result.tool_version, result.endpoint, paginated=True)

    def graphql(
        self,
        query: str,
        *,
        variables: dict[str, str] | None = None,
        maximum_output_bytes: int = MAX_API_RESPONSE_BYTES,
    ) -> GhResult:
        tool_version = self._tool_version or self.check_environment()
        args = ["gh", "api", "graphql", "--raw-field", f"query={query}"]
        for key, value in sorted((variables or {}).items()):
            args.extend(("--raw-field", f"{key}={value}"))
        completed = self._run(tuple(args), operation="graphql")
        if completed.returncode != 0:
            self._raise_api_failure("graphql", completed)
        if len(completed.stdout.encode("utf-8")) > maximum_output_bytes:
            raise GitHubSchemaError(
                code="github_response_too_large",
                message=(
                    "GitHub GraphQL response exceeded the "
                    f"{maximum_output_bytes}-byte safety limit."
                ),
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise GitHubSchemaError(
                code="github_invalid_json",
                message="GitHub GraphQL returned invalid JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise GitHubSchemaError(
                code="github_schema_mismatch",
                message="GitHub GraphQL response was not an object.",
            )
        errors = payload.get("errors")
        if errors:
            diagnostic = _redact(json.dumps(errors, ensure_ascii=False)[:500])
            lowered = diagnostic.casefold()
            if "rate limit" in lowered:
                raise GitHubRateLimitError(
                    code="github_rate_limited",
                    message="GitHub rate-limited the GraphQL read.",
                )
            if "authentication" in lowered or "unauthorized" in lowered:
                raise GitHubAuthError(
                    code="github_auth_failed",
                    message="GitHub authentication failed during the GraphQL read.",
                )
            raise GitHubSchemaError(
                code="github_graphql_error",
                message=f"GitHub GraphQL rejected the read: {diagnostic}",
            )
        if not isinstance(payload.get("data"), dict):
            raise GitHubSchemaError(
                code="github_schema_mismatch",
                message="GitHub GraphQL response omitted its data object.",
            )
        return GhResult(payload, tool_version, "graphql", paginated=False)

    def api_version_probe(self) -> GhResult:
        return self._api_json("meta")

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
        maximum_output_bytes: int = MAX_API_RESPONSE_BYTES,
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
        if len(completed.stdout.encode("utf-8")) > maximum_output_bytes:
            raise GitHubSchemaError(
                code="github_response_too_large",
                message=(
                    f"GitHub response for {endpoint} exceeded the "
                    f"{maximum_output_bytes}-byte safety limit."
                ),
                details={"endpoint": endpoint, "maximum_bytes": maximum_output_bytes},
            )
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

    def _read_tool_version(self) -> str:
        if self._tool_version is not None:
            return self._tool_version
        version = self._run(("gh", "--version"), operation="version")
        first_line = version.stdout.splitlines()[0] if version.stdout else ""
        if not first_line.startswith("gh version "):
            raise GitHubSchemaError(
                code="github_version_unrecognized",
                message="The installed gh CLI returned an unrecognized version response.",
            )
        self._tool_version = first_line.removeprefix("gh version ").split()[0]
        return self._tool_version

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
        if "http 404" in lowered or "not found" in lowered:
            raise GitHubNotFoundError(
                code="github_not_found",
                message=f"GitHub did not expose the requested resource at {endpoint}.",
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
