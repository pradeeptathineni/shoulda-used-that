from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from typing import Any

import pytest

from shoulda_used_that.errors import (
    GitHubAuthError,
    GitHubError,
    GitHubRateLimitError,
    GitHubSchemaError,
)
from shoulda_used_that.github_mutations import GhMutationClient


def _completed(
    args: tuple[str, ...], *, code: int = 0, out: str = "", err: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=code, stdout=out, stderr=err)


def _runner(
    responses: list[subprocess.CompletedProcess[str]],
    captured: list[tuple[tuple[str, ...], dict[str, Any]]],
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run(args: tuple[str, ...], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured.append((args, kwargs))
        return responses.pop(0)

    return run


def test_mutation_adapter_emits_only_additive_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    create_payload = {
        "data": {
            "createUserList": {
                "clientMutationId": "cmid_create",
                "list": {
                    "id": "L1",
                    "name": "Public tools",
                    "description": "Reviewed public tools.",
                    "isPrivate": False,
                    "slug": "public-tools",
                },
            }
        }
    }
    membership_payload = {
        "data": {
            "updateUserListsForItem": {
                "clientMutationId": "cmid_membership",
                "item": {
                    "__typename": "Repository",
                    "id": "R1",
                    "nameWithOwner": "fixture/repo",
                },
                "lists": [{"id": "L1"}, {"id": "L_private"}],
            }
        }
    }
    monkeypatch.setattr(
        "shoulda_used_that.github.subprocess.run",
        _runner(
            [
                _completed(("gh",)),
                _completed(("gh",), out=json.dumps(create_payload)),
                _completed(("gh",), out=json.dumps(membership_payload)),
            ],
            captured,
        ),
    )
    client = GhMutationClient()
    client._tool_version = "2.test"

    client.star_repository("Fixture/Repo")
    created = client.create_user_list(
        name="Public tools",
        description="Reviewed public tools.",
        client_mutation_id="cmid_create",
    )
    membership = client.update_user_lists_for_item(
        repository_node_id="R1",
        list_ids=("L_private", "L1", "L1"),
        client_mutation_id="cmid_membership",
    )

    assert created.node_id == "L1"
    assert membership.list_ids == ("L1", "L_private")
    star_args = captured[0][0]
    assert "PUT" in star_args
    assert "user/starred/fixture/repo" in star_args
    create_args = captured[1][0]
    assert "createUserList" in " ".join(create_args)
    assert "isPrivate=false" in create_args
    membership_args = captured[2][0]
    assert "listIds[]=L1" in membership_args
    assert "listIds[]=L_private" in membership_args
    all_arguments = " ".join(argument for call, _ in captured for argument in call)
    for forbidden in (
        "DELETE",
        "unstar",
        "deleteUserList",
        "updateUserList(",
        "remove-list-membership",
    ):
        assert forbidden not in all_arguments


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (
            {
                "data": {
                    "createUserList": {
                        "clientMutationId": "wrong",
                        "list": {},
                    }
                }
            },
            "github_mutation_identity_mismatch",
        ),
        (
            {
                "data": {
                    "createUserList": {
                        "clientMutationId": "cmid",
                        "list": {
                            "id": "L1",
                            "name": "Name",
                            "description": "Description",
                            "isPrivate": True,
                            "slug": "name",
                        },
                    }
                }
            },
            "github_mutation_postcondition_mismatch",
        ),
        ({"data": {"createUserList": None}}, "github_mutation_schema_invalid"),
    ],
)
def test_create_list_response_is_verified(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any], code: str
) -> None:
    captured: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    monkeypatch.setattr(
        "shoulda_used_that.github.subprocess.run",
        _runner([_completed(("gh",), out=json.dumps(payload))], captured),
    )
    client = GhMutationClient()
    client._tool_version = "2.test"
    with pytest.raises(GitHubSchemaError) as raised:
        client.create_user_list(name="Name", description="Description", client_mutation_id="cmid")
    assert raised.value.code == code


def test_membership_response_must_echo_identity_and_exact_union(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    payload = {
        "data": {
            "updateUserListsForItem": {
                "clientMutationId": "cmid",
                "item": {
                    "__typename": "Repository",
                    "id": "R1",
                    "nameWithOwner": "fixture/repo",
                },
                "lists": [{"id": "L1"}],
            }
        }
    }
    monkeypatch.setattr(
        "shoulda_used_that.github.subprocess.run",
        _runner([_completed(("gh",), out=json.dumps(payload))], captured),
    )
    client = GhMutationClient()
    client._tool_version = "2.test"
    with pytest.raises(GitHubSchemaError) as raised:
        client.update_user_lists_for_item(
            repository_node_id="R1",
            list_ids=("L1", "L2"),
            client_mutation_id="cmid",
        )
    assert raised.value.code == "github_mutation_postcondition_mismatch"
    with pytest.raises(ValueError, match="at least one List ID"):
        client.update_user_lists_for_item(
            repository_node_id="R1",
            list_ids=(),
            client_mutation_id="cmid",
        )


@pytest.mark.parametrize(
    ("output", "error_type", "code"),
    [
        ("{", GitHubSchemaError, "github_invalid_json"),
        ("[]", GitHubSchemaError, "github_schema_mismatch"),
        (
            '{"errors": [{"message": "rate limit"}]}',
            GitHubRateLimitError,
            "github_rate_limited",
        ),
        (
            '{"errors": [{"message": "authentication required"}]}',
            GitHubAuthError,
            "github_auth_failed",
        ),
        (
            '{"errors": [{"message": "preview changed"}]}',
            GitHubSchemaError,
            "github_graphql_error",
        ),
        ('{"data": null}', GitHubSchemaError, "github_schema_mismatch"),
    ],
)
def test_graphql_mutation_failures_are_typed(
    monkeypatch: pytest.MonkeyPatch,
    output: str,
    error_type: type[GitHubError],
    code: str,
) -> None:
    captured: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    monkeypatch.setattr(
        "shoulda_used_that.github.subprocess.run",
        _runner([_completed(("gh",), out=output)], captured),
    )
    client = GhMutationClient()
    client._tool_version = "2.test"
    with pytest.raises(error_type) as raised:
        client.create_user_list(name="Name", description="Description", client_mutation_id="cmid")
    assert raised.value.code == code


def test_star_response_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    monkeypatch.setattr(
        "shoulda_used_that.github.subprocess.run",
        _runner([_completed(("gh",), out="x" * 1025)], captured),
    )
    client = GhMutationClient()
    client._tool_version = "2.test"
    with pytest.raises(GitHubSchemaError) as raised:
        client.star_repository("fixture/repo")
    assert raised.value.code == "github_mutation_response_too_large"
