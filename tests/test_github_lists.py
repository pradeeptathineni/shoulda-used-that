from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from shoulda_used_that.errors import GitHubAuthError, GitHubError, GitHubSchemaError
from shoulda_used_that.github import GhAuthStatus, GhResult
from shoulda_used_that.github_lists import (
    GitHubCapabilityState,
    GitHubCurationState,
    _integer,
    _mapping,
    _page_info,
    _parse_list_items,
    _repository_from_rest,
    probe_capabilities,
    read_curation_state,
    read_starred,
    read_user_lists,
)
from shoulda_used_that.github_lists import (
    _list as _require_list_value,
)

NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)


class FakeGitHub:
    def __init__(self) -> None:
        self.auth: GhAuthStatus | BaseException = GhAuthStatus(
            login="fixture-user",
            host="github.com",
            scopes=("repo", "user"),
            token_source="fixture",
            tool_version="2.test",
        )
        self.graphql_results: list[GhResult | BaseException] = []
        self.rest_probe: GhResult | BaseException = _result(
            {"verifiable_password_authentication": True}
        )
        self.viewer_stars = _result([])
        self.public_stars = _result([])
        self.repositories: dict[str, GhResult] = {}
        self.calls: list[tuple[str, Any]] = []

    def auth_status(self) -> GhAuthStatus:
        self.calls.append(("auth", None))
        if isinstance(self.auth, BaseException):
            raise self.auth
        return self.auth

    def graphql(
        self,
        query: str,
        *,
        variables: dict[str, str] | None = None,
        maximum_output_bytes: int = 20 * 1024 * 1024,
    ) -> GhResult:
        self.calls.append(("graphql", (query, variables, maximum_output_bytes)))
        result = self.graphql_results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    def api_version_probe(self) -> GhResult:
        self.calls.append(("api-version", None))
        if isinstance(self.rest_probe, BaseException):
            raise self.rest_probe
        return self.rest_probe

    def starred(self) -> GhResult:
        self.calls.append(("viewer-stars", None))
        return self.viewer_stars

    def user_starred(self, login: str) -> GhResult:
        self.calls.append(("public-stars", login))
        return self.public_stars

    def repository(self, repository: str) -> GhResult:
        self.calls.append(("repository", repository))
        return self.repositories[repository]


def _result(payload: Any) -> GhResult:
    return GhResult(payload=payload, tool_version="2.test", endpoint="fixture", paginated=False)


def _capability_payload(*, item_types: tuple[str, ...] = ("Repository",)) -> dict[str, Any]:
    return {
        "data": {
            "viewer": {"login": "fixture-user", "id": "U_fixture"},
            "userType": {"fields": [{"name": "login"}, {"name": "lists"}]},
            "itemType": {
                "kind": "UNION",
                "possibleTypes": [{"name": item} for item in item_types],
            },
            "mutationType": {
                "fields": [
                    {"name": "createUserList"},
                    {"name": "updateUserListsForItem"},
                ]
            },
            "createInput": {
                "inputFields": [
                    {"name": "name"},
                    {"name": "description"},
                    {"name": "isPrivate"},
                ]
            },
            "membershipInput": {"inputFields": [{"name": "itemId"}, {"name": "listIds"}]},
        }
    }


def _repository(
    name: str,
    node_id: str,
    *,
    private: bool = False,
    archived: bool = False,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "node_id": node_id,
        "nameWithOwner": name,
        "full_name": name,
        "isPrivate": private,
        "private": private,
        "isArchived": archived,
        "archived": archived,
        "url": f"https://github.com/{name}",
        "html_url": f"https://github.com/{name}",
    }


def _list(
    node_id: str,
    name: str,
    *,
    nodes: list[dict[str, Any]],
    total: int | None = None,
    has_next: bool = False,
    cursor: str | None = None,
    private: bool = False,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "name": name,
        "description": f"{name} description",
        "isPrivate": private,
        "slug": name.casefold().replace(" ", "-"),
        "items": {
            "totalCount": len(nodes) if total is None else total,
            "nodes": nodes,
            "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
        },
    }


def _owner_page(
    *,
    key: str,
    lists: list[dict[str, Any]],
    total: int | None = None,
    has_next: bool = False,
    cursor: str | None = None,
) -> dict[str, Any]:
    return {
        "data": {
            key: {
                "login": "fixture-user",
                "id": "U_fixture",
                "lists": {
                    "totalCount": len(lists) if total is None else total,
                    "nodes": lists,
                    "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                },
            }
        }
    }


def test_capability_probe_reports_available_missing_scope_and_preview_change() -> None:
    available_client = FakeGitHub()
    available_client.graphql_results = [_result(_capability_payload())]
    available = probe_capabilities(available_client, observed_at=NOW)
    assert available.state is GitHubCapabilityState.AVAILABLE
    assert available.login == "fixture-user"
    assert available.node_id == "U_fixture"
    assert available.operator_command is None
    assert available.rest_api_probe_passed is True

    missing_client = FakeGitHub()
    missing_client.auth = GhAuthStatus("fixture-user", "github.com", ("repo",), "fixture", "2.test")
    missing_client.graphql_results = [_result(_capability_payload())]
    missing = probe_capabilities(missing_client, observed_at=NOW)
    assert missing.state is GitHubCapabilityState.MISSING_SCOPE
    assert missing.missing_scopes == ("user",)
    assert missing.operator_command == "gh auth refresh --hostname github.com -s user"

    changed_client = FakeGitHub()
    changed_client.graphql_results = [
        _result(_capability_payload(item_types=("Repository", "FutureItem")))
    ]
    changed = probe_capabilities(changed_client, observed_at=NOW)
    assert changed.state is GitHubCapabilityState.PREVIEW_CHANGED
    assert changed.repository_item_union_exact is False


def test_capability_probe_classifies_auth_and_transport_failures() -> None:
    unauthenticated = FakeGitHub()
    unauthenticated.auth = GitHubAuthError("github_auth_inactive", "not logged in")
    result = probe_capabilities(unauthenticated, observed_at=NOW)
    assert result.state is GitHubCapabilityState.UNAUTHENTICATED
    assert result.error_code == "github_auth_inactive"
    assert result.login == ""

    unavailable = FakeGitHub()
    unavailable.graphql_results = [GitHubError("github_timeout", "timed out")]
    result = probe_capabilities(unavailable, observed_at=NOW)
    assert result.state is GitHubCapabilityState.UNAVAILABLE
    assert result.error_code == "github_timeout"
    assert result.rest_api_probe_passed is True


def test_viewer_lists_paginate_outer_and_item_connections_without_loss() -> None:
    client = FakeGitHub()
    first_repository = {"__typename": "Repository", **_repository("a/one", "R1")}
    second_repository = {"__typename": "Repository", **_repository("a/two", "R2")}
    first_list = _list(
        "L1",
        "One",
        nodes=[first_repository],
        total=2,
        has_next=True,
        cursor="item-cursor",
    )
    second_list = _list("L2", "Empty", nodes=[])
    client.graphql_results = [
        _result(
            _owner_page(
                key="viewer",
                lists=[first_list],
                total=2,
                has_next=True,
                cursor="list-cursor",
            )
        ),
        _result(
            {
                "data": {
                    "node": {
                        "__typename": "UserList",
                        "items": {
                            "totalCount": 2,
                            "nodes": [second_repository],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        },
                    }
                }
            }
        ),
        _result(_owner_page(key="viewer", lists=[second_list], total=2)),
    ]

    collection = read_user_lists(client, login="fixture-user", viewer=True)

    assert collection.node_id == "U_fixture"
    assert [item.name for item in collection.lists] == ["Empty", "One"]
    assert [item.repository for item in collection.lists[1].members] == ["a/one", "a/two"]
    graphql_variables = [call[1][1] for call in client.calls if call[0] == "graphql"]
    assert graphql_variables == [{}, {"id": "L1", "after": "item-cursor"}, {"after": "list-cursor"}]


def test_public_lists_zero_empty_and_unknown_union_items_are_explicit() -> None:
    zero_client = FakeGitHub()
    zero_client.graphql_results = [_result(_owner_page(key="user", lists=[]))]
    zero = read_user_lists(zero_client, login="fixture-user", viewer=False)
    assert zero.lists == ()
    assert zero_client.calls[0][1][1] == {"login": "fixture-user"}

    unknown_client = FakeGitHub()
    future_list = _list(
        "L1",
        "Future",
        nodes=[{"__typename": "FutureListItem"}],
    )
    unknown_client.graphql_results = [_result(_owner_page(key="viewer", lists=[future_list]))]
    collection = read_user_lists(unknown_client, login="fixture-user", viewer=True)
    assert collection.lists[0].members == ()
    assert collection.lists[0].unknown_item_types == ("FutureListItem",)


def test_list_pagination_and_duplicate_failures_are_typed() -> None:
    repeated = FakeGitHub()
    repeated.graphql_results = [
        _result(_owner_page(key="viewer", lists=[], total=1, has_next=True, cursor="same")),
        _result(_owner_page(key="viewer", lists=[], total=1, has_next=True, cursor="same")),
    ]
    with pytest.raises(GitHubSchemaError) as pagination:
        read_user_lists(repeated, login="fixture-user", viewer=True)
    assert pagination.value.code == "github_pagination_invalid"

    conflict = FakeGitHub()
    first = _list("L1", "First", nodes=[])
    changed = _list("L1", "Changed", nodes=[])
    conflict.graphql_results = [
        _result(_owner_page(key="viewer", lists=[first], total=1, has_next=True, cursor="next")),
        _result(_owner_page(key="viewer", lists=[changed], total=1)),
    ]
    with pytest.raises(GitHubSchemaError) as duplicate:
        read_user_lists(conflict, login="fixture-user", viewer=True)
    assert duplicate.value.code == "github_list_duplicate_conflict"


def test_timestamped_and_public_stars_have_distinct_complete_shapes() -> None:
    client = FakeGitHub()
    repository = _repository("a/one", "R1")
    client.viewer_stars = _result([{"starred_at": "2026-09-17T10:00:00Z", "repo": repository}])
    client.public_stars = _result([repository])

    viewer = read_starred(client, login="fixture-user", viewer=True)
    public = read_starred(client, login="fixture-user", viewer=False)

    assert viewer[0].starred_at == datetime(2026, 9, 17, 10, tzinfo=UTC)
    assert public[0].starred_at is None
    assert [call[0] for call in client.calls] == ["viewer-stars", "public-stars"]


def test_read_curation_state_joins_stars_metadata_lists_and_stable_identity() -> None:
    client = FakeGitHub()
    starred = _repository("a/starred", "R1")
    client.viewer_stars = _result([{"starred_at": "2026-09-17T10:00:00Z", "repo": starred}])
    client.graphql_results = [_result(_owner_page(key="viewer", lists=[]))]
    client.repositories["a/new"] = _result(_repository("a/new", "R2"))

    state = read_curation_state(
        client,
        account="fixture-user",
        desired_repositories=("a/new", "a/starred"),
        observed_at=NOW,
    )

    assert state.total_starred_count == 1
    assert [(item.repository, item.starred) for item in state.relevant_repositories] == [
        ("a/new", False),
        ("a/starred", True),
    ]
    assert state.state_fingerprint.startswith("github_")
    assert ("repository", "a/new") in client.calls
    assert ("repository", "a/starred") not in client.calls


def test_capability_probe_preserves_typed_schema_diagnostics() -> None:
    invalid_rest = FakeGitHub()
    invalid_rest.rest_probe = _result([])
    result = probe_capabilities(invalid_rest, observed_at=NOW)
    assert result.state is GitHubCapabilityState.UNAVAILABLE
    assert result.error_code == "github_api_version_probe_invalid"
    assert result.rest_api_probe_passed is False

    identity_mismatch = FakeGitHub()
    payload = _capability_payload()
    payload["data"]["viewer"]["login"] = "another-user"
    identity_mismatch.graphql_results = [_result(payload)]
    result = probe_capabilities(identity_mismatch, observed_at=NOW)
    assert result.state is GitHubCapabilityState.UNAVAILABLE
    assert result.error_code == "github_identity_mismatch"

    missing_identity = FakeGitHub()
    payload = _capability_payload()
    del payload["data"]["viewer"]["id"]
    missing_identity.graphql_results = [_result(payload)]
    result = probe_capabilities(missing_identity, observed_at=NOW)
    assert result.error_code == "github_viewer_schema_invalid"


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"data": {"user": None}}, "github_user_not_found"),
        (
            {
                "data": {
                    "viewer": {
                        "login": "fixture-user",
                        "lists": {},
                        "id": None,
                    }
                }
            },
            "github_lists_schema_invalid",
        ),
        (
            _owner_page(key="viewer", lists=[])
            | {
                "data": {
                    "viewer": {
                        **_owner_page(key="viewer", lists=[])["data"]["viewer"],
                        "login": "another-user",
                    }
                }
            },
            "github_identity_mismatch",
        ),
        (_owner_page(key="viewer", lists=[], total=1), "github_pagination_incomplete"),
    ],
)
def test_list_owner_and_completeness_faults_are_typed(payload: dict[str, Any], code: str) -> None:
    client = FakeGitHub()
    client.graphql_results = [_result(payload)]
    with pytest.raises(GitHubSchemaError) as raised:
        read_user_lists(
            client,
            login="fixture-user",
            viewer="viewer" in payload.get("data", {}),
        )
    assert raised.value.code == code


def test_list_and_item_schema_faults_are_typed() -> None:
    malformed_list = FakeGitHub()
    invalid = _list("L1", "Invalid", nodes=[])
    invalid["isPrivate"] = "no"
    malformed_list.graphql_results = [_result(_owner_page(key="viewer", lists=[invalid]))]
    with pytest.raises(GitHubSchemaError) as list_schema:
        read_user_lists(malformed_list, login="fixture-user", viewer=True)
    assert list_schema.value.code == "github_lists_schema_invalid"

    incomplete_items = FakeGitHub()
    incomplete = _list("L1", "Incomplete", nodes=[], total=1)
    incomplete_items.graphql_results = [_result(_owner_page(key="viewer", lists=[incomplete]))]
    with pytest.raises(GitHubSchemaError) as incomplete_error:
        read_user_lists(incomplete_items, login="fixture-user", viewer=True)
    assert incomplete_error.value.code == "github_pagination_incomplete"

    no_cursor = FakeGitHub()
    paged = _list("L1", "Paged", nodes=[], total=1, has_next=True, cursor=None)
    no_cursor.graphql_results = [_result(_owner_page(key="viewer", lists=[paged]))]
    with pytest.raises(GitHubSchemaError) as cursor_error:
        read_user_lists(no_cursor, login="fixture-user", viewer=True)
    assert cursor_error.value.code == "github_pagination_invalid"


def test_low_level_schema_guards_reject_unknown_or_malformed_values() -> None:
    for callback in (
        lambda: _mapping([], "fixture"),
        lambda: _require_list_value({}, "fixture"),
        lambda: _integer(True, "fixture"),
        lambda: _page_info({"hasNextPage": "yes", "endCursor": None}, "fixture"),
        lambda: _parse_list_items([{}]),
        lambda: _parse_list_items([{"__typename": "Repository"}]),
        lambda: _repository_from_rest({}, starred_at=None),
    ):
        with pytest.raises(GitHubSchemaError):
            callback()


def test_star_and_repository_identity_conflicts_fail_closed() -> None:
    missing_timestamp = FakeGitHub()
    missing_timestamp.viewer_stars = _result([{"repo": _repository("a/one", "R1")}])
    with pytest.raises(GitHubSchemaError) as timestamp:
        read_starred(missing_timestamp, login="fixture-user", viewer=True)
    assert timestamp.value.code == "github_star_schema_invalid"

    duplicate = FakeGitHub()
    duplicate.public_stars = _result([_repository("a/one", "R1"), _repository("a/one", "R2")])
    with pytest.raises(GitHubSchemaError) as conflict:
        read_starred(duplicate, login="fixture-user", viewer=False)
    assert conflict.value.code == "github_star_duplicate_conflict"

    renamed = FakeGitHub()
    renamed.viewer_stars = _result([])
    renamed.graphql_results = [_result(_owner_page(key="viewer", lists=[]))]
    renamed.repositories["a/old"] = _result(_repository("a/new", "R1"))
    with pytest.raises(GitHubSchemaError) as identity:
        read_curation_state(
            renamed,
            account="fixture-user",
            desired_repositories=("a/old",),
            observed_at=NOW,
        )
    assert identity.value.code == "github_repository_identity_mismatch"


def test_github_state_fingerprint_is_validated_on_read() -> None:
    client = FakeGitHub()
    client.viewer_stars = _result([])
    client.graphql_results = [_result(_owner_page(key="viewer", lists=[]))]
    state = read_curation_state(
        client,
        account="fixture-user",
        desired_repositories=(),
        observed_at=NOW,
    )
    payload = state.model_dump(mode="json")
    payload["state_fingerprint"] = "github_" + ("0" * 64)
    with pytest.raises(ValidationError):
        GitHubCurationState.model_validate(payload)
