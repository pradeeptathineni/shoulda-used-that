from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from shoulda_used_that.errors import (
    GitHubAuthError,
    GitHubError,
    GitHubPartialError,
    GitHubRateLimitError,
    GitHubSchemaError,
)
from shoulda_used_that.github import API_VERSION, STAR_ACCEPT, GhClient


def _completed(args: tuple[str, ...], *, code: int = 0, out: str = "", err: str = "") -> Any:
    return subprocess.CompletedProcess(args=args, returncode=code, stdout=out, stderr=err)


def _runner(
    responses: list[Any], captured: list[tuple[tuple[str, ...], dict[str, Any]]]
) -> Callable[..., Any]:
    def run(args: tuple[str, ...], **kwargs: Any) -> Any:
        captured.append((args, kwargs))
        response = responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    return run


def test_repository_uses_fixed_argument_vector_headers_and_minimal_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    responses = [
        _completed(("gh",), out="gh version 2.101.0 (test)\n"),
        _completed(("gh",), out="github.com logged in\n"),
        _completed(("gh",), out=json.dumps({"full_name": "fixture-labs/repo"})),
    ]
    monkeypatch.setattr("shoulda_used_that.github.subprocess.run", _runner(responses, captured))
    monkeypatch.setenv("GH_TOKEN", "must-not-be-forwarded")
    client = GhClient(timeout_seconds=4, cwd=tmp_path)

    result = client.repository("https://github.com/Fixture-Labs/Repo.git/")

    assert result.payload["full_name"] == "fixture-labs/repo"
    api_args, kwargs = captured[-1]
    assert api_args[:5] == ("gh", "api", "--method", "GET", "--header")
    assert "repos/fixture-labs/repo" in api_args
    assert f"X-GitHub-Api-Version: {API_VERSION}" in api_args
    assert "GH_TOKEN" not in kwargs["env"]
    assert kwargs["shell"] is False if "shell" in kwargs else True
    assert kwargs["timeout"] == 4
    assert kwargs["cwd"] == tmp_path


def test_search_is_bounded_and_stars_require_complete_paginated_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    responses = [
        _completed(("gh",), out='{"items": [{"full_name": "a/b"}]}'),
        _completed(("gh",), out='[[{"repo": {"full_name": "a/b"}}]]'),
    ]
    monkeypatch.setattr("shoulda_used_that.github.subprocess.run", _runner(responses, captured))
    client = GhClient()
    client._tool_version = "2.test"

    assert len(client.search("topic:receipts", maximum=2).payload) == 1
    assert "q=topic:receipts" in captured[0][0]
    assert "per_page=2" in captured[0][0]
    assert client.starred().paginated is True
    assert "--paginate" in captured[1][0]
    assert "--slurp" in captured[1][0]
    assert f"Accept: {STAR_ACCEPT}" in captured[1][0]
    with pytest.raises(ValueError, match="1 to 100"):
        client.search("x", maximum=101)


@pytest.mark.parametrize(
    ("stderr", "error_type", "code"),
    [
        ("HTTP 429 rate limit", GitHubRateLimitError, "github_rate_limited"),
        ("HTTP 401 bad credentials", GitHubAuthError, "github_auth_failed"),
        ("HTTP 500 token: secret", GitHubError, "github_transport_failed"),
    ],
)
def test_api_failures_are_typed_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
    stderr: str,
    error_type: type[GitHubError],
    code: str,
) -> None:
    captured: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    monkeypatch.setattr(
        "shoulda_used_that.github.subprocess.run",
        _runner([_completed(("gh",), code=1, err=stderr)], captured),
    )
    client = GhClient()
    client._tool_version = "2.test"

    with pytest.raises(error_type) as raised:
        client.repository("a/b")

    assert raised.value.code == code
    assert "secret" not in raised.value.message


def test_fine_grained_token_is_redacted_from_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    token = "github_pat_never_expose_this"
    monkeypatch.setattr(
        "shoulda_used_that.github.subprocess.run",
        _runner([_completed(("gh",), code=1, err=f"HTTP 500 {token}")], captured),
    )
    client = GhClient()
    client._tool_version = "2.test"

    with pytest.raises(GitHubError) as raised:
        client.repository("a/b")

    assert token not in raised.value.message
    assert "[REDACTED]" in raised.value.message


def test_invalid_json_and_schema_never_return_partial_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    monkeypatch.setattr(
        "shoulda_used_that.github.subprocess.run",
        _runner([_completed(("gh",), out="{")], captured),
    )
    client = GhClient()
    client._tool_version = "2.test"
    with pytest.raises(GitHubPartialError):
        client.starred()

    monkeypatch.setattr(
        "shoulda_used_that.github.subprocess.run",
        _runner([_completed(("gh",), out="[]")], captured),
    )
    with pytest.raises(GitHubSchemaError) as raised:
        client.search("x")
    assert raised.value.code == "github_schema_mismatch"


def test_missing_timeout_auth_and_version_failures_are_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    monkeypatch.setattr(
        "shoulda_used_that.github.subprocess.run",
        _runner([FileNotFoundError("gh")], captured),
    )
    with pytest.raises(GitHubAuthError) as missing:
        GhClient().check_environment()
    assert missing.value.code == "github_cli_missing"

    monkeypatch.setattr(
        "shoulda_used_that.github.subprocess.run",
        _runner([subprocess.TimeoutExpired(("gh",), 1)], captured),
    )
    with pytest.raises(GitHubError) as timeout:
        GhClient().check_environment()
    assert timeout.value.code == "github_timeout"

    responses = [
        _completed(("gh",), out="gh version 2.test\n"),
        _completed(("gh",), code=1, err="not logged in"),
    ]
    monkeypatch.setattr("shoulda_used_that.github.subprocess.run", _runner(responses, captured))
    with pytest.raises(GitHubAuthError) as auth:
        GhClient().check_environment()
    assert auth.value.code == "github_auth_inactive"

    monkeypatch.setattr(
        "shoulda_used_that.github.subprocess.run",
        _runner([_completed(("gh",), out="unexpected\n")], captured),
    )
    with pytest.raises(GitHubSchemaError) as version:
        GhClient().check_environment()
    assert version.value.code == "github_version_unrecognized"


def test_conditional_empty_response_reports_not_modified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    monkeypatch.setattr(
        "shoulda_used_that.github.subprocess.run",
        _runner([_completed(("gh",), out="")], captured),
    )
    client = GhClient()
    client._tool_version = "2.test"
    result = client._api_json("repos/a/b", etag='"abc"')
    assert result.payload == {"not_modified": True}
    assert 'If-None-Match: "abc"' in captured[0][0]
