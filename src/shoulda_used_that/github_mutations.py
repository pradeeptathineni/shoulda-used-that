"""Narrow additive-only GitHub mutation adapter for approved sealed plans."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from shoulda_used_that.errors import (
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubSchemaError,
)
from shoulda_used_that.github import (
    API_VERSION,
    DEFAULT_ACCEPT,
    MAX_API_RESPONSE_BYTES,
    GhClient,
    _redact,
)
from shoulda_used_that.github_lists import GitHubReadClient
from shoulda_used_that.models import normalize_repository

CREATE_LIST_MUTATION = """
mutation($name: String!, $description: String!, $isPrivate: Boolean!, $clientMutationId: String!) {
  createUserList(input: {
    name: $name,
    description: $description,
    isPrivate: $isPrivate,
    clientMutationId: $clientMutationId
  }) {
    clientMutationId
    list { id name description isPrivate slug }
  }
}
"""
UPDATE_MEMBERSHIPS_MUTATION = """
mutation($itemId: ID!, $listIds: [ID!]!, $clientMutationId: String!) {
  updateUserListsForItem(input: {
    itemId: $itemId,
    listIds: $listIds,
    clientMutationId: $clientMutationId
  }) {
    clientMutationId
    item { __typename ... on Repository { id nameWithOwner } }
    lists { id }
  }
}
"""


@dataclass(frozen=True, slots=True)
class CreatedUserList:
    node_id: str
    name: str
    description: str
    is_private: bool
    slug: str
    client_mutation_id: str


@dataclass(frozen=True, slots=True)
class MembershipMutationResult:
    repository_node_id: str
    repository: str
    list_ids: tuple[str, ...]
    client_mutation_id: str


class GitHubApplyClient(GitHubReadClient, Protocol):
    def star_repository(self, repository: str) -> None: ...

    def create_user_list(
        self,
        *,
        name: str,
        description: str,
        client_mutation_id: str,
    ) -> CreatedUserList: ...

    def update_user_lists_for_item(
        self,
        *,
        repository_node_id: str,
        list_ids: tuple[str, ...],
        client_mutation_id: str,
    ) -> MembershipMutationResult: ...


class GhMutationClient(GhClient):
    """Expose only star, public-List create, and membership-union writes."""

    def star_repository(self, repository: str) -> None:
        canonical = normalize_repository(repository)
        self._tool_version = self._tool_version or self.check_environment()
        endpoint = f"user/starred/{canonical}"
        completed = self._run(
            (
                "gh",
                "api",
                "--method",
                "PUT",
                "--header",
                f"Accept: {DEFAULT_ACCEPT}",
                "--header",
                f"X-GitHub-Api-Version: {API_VERSION}",
                endpoint,
            ),
            operation=f"star:{canonical}",
        )
        if completed.returncode != 0:
            self._raise_api_failure(endpoint, completed)
        if len(completed.stdout.encode("utf-8")) > 1024:
            raise GitHubSchemaError(
                code="github_mutation_response_too_large",
                message="GitHub star response exceeded its safety limit.",
            )

    def create_user_list(
        self,
        *,
        name: str,
        description: str,
        client_mutation_id: str,
    ) -> CreatedUserList:
        payload = self._graphql_write(
            CREATE_LIST_MUTATION,
            raw_fields={
                "name": name,
                "description": description,
                "clientMutationId": client_mutation_id,
            },
            typed_fields=("isPrivate=false",),
            operation="create-user-list",
        )
        data = _mapping(payload.get("data"), "mutation data")
        result = _mapping(data.get("createUserList"), "createUserList payload")
        if result.get("clientMutationId") != client_mutation_id:
            raise GitHubSchemaError(
                code="github_mutation_identity_mismatch",
                message="GitHub did not echo the sealed List-create client mutation ID.",
            )
        github_list = _mapping(result.get("list"), "created UserList")
        node_id = github_list.get("id")
        observed_name = github_list.get("name")
        observed_description = github_list.get("description")
        is_private = github_list.get("isPrivate")
        slug = github_list.get("slug")
        if (
            not isinstance(node_id, str)
            or not isinstance(observed_name, str)
            or not isinstance(observed_description, str)
            or not isinstance(is_private, bool)
            or not isinstance(slug, str)
        ):
            raise GitHubSchemaError(
                code="github_mutation_schema_invalid",
                message="GitHub List-create response omitted a required typed field.",
            )
        if observed_name != name or observed_description != description or is_private:
            raise GitHubSchemaError(
                code="github_mutation_postcondition_mismatch",
                message="GitHub List-create response did not match the exact public List request.",
            )
        return CreatedUserList(
            node_id=node_id,
            name=observed_name,
            description=observed_description,
            is_private=is_private,
            slug=slug,
            client_mutation_id=client_mutation_id,
        )

    def update_user_lists_for_item(
        self,
        *,
        repository_node_id: str,
        list_ids: tuple[str, ...],
        client_mutation_id: str,
    ) -> MembershipMutationResult:
        stable_list_ids = tuple(sorted(set(list_ids)))
        if not repository_node_id or not stable_list_ids:
            raise ValueError("membership update requires an item ID and at least one List ID")
        payload = self._graphql_write(
            UPDATE_MEMBERSHIPS_MUTATION,
            raw_fields={
                "itemId": repository_node_id,
                "clientMutationId": client_mutation_id,
            },
            typed_fields=tuple(f"listIds[]={item}" for item in stable_list_ids),
            operation="update-user-list-memberships",
        )
        data = _mapping(payload.get("data"), "mutation data")
        result = _mapping(data.get("updateUserListsForItem"), "updateUserListsForItem payload")
        if result.get("clientMutationId") != client_mutation_id:
            raise GitHubSchemaError(
                code="github_mutation_identity_mismatch",
                message="GitHub did not echo the sealed membership client mutation ID.",
            )
        item = _mapping(result.get("item"), "updated List item")
        node_id = item.get("id")
        repository = item.get("nameWithOwner")
        if (
            item.get("__typename") != "Repository"
            or not isinstance(node_id, str)
            or not isinstance(repository, str)
        ):
            raise GitHubSchemaError(
                code="github_mutation_schema_invalid",
                message="GitHub membership response did not return a repository item.",
            )
        if node_id != repository_node_id:
            raise GitHubSchemaError(
                code="github_mutation_identity_mismatch",
                message="GitHub membership response returned a different repository node.",
            )
        raw_lists = _list(result.get("lists"), "updated Lists")
        observed_list_ids: list[str] = []
        for raw_list in raw_lists:
            list_payload = _mapping(raw_list, "updated UserList")
            list_id = list_payload.get("id")
            if not isinstance(list_id, str):
                raise GitHubSchemaError(
                    code="github_mutation_schema_invalid",
                    message="GitHub membership response omitted a List node ID.",
                )
            observed_list_ids.append(list_id)
        if set(observed_list_ids) != set(stable_list_ids):
            raise GitHubSchemaError(
                code="github_mutation_postcondition_mismatch",
                message="GitHub membership response did not preserve the requested List union.",
            )
        return MembershipMutationResult(
            repository_node_id=node_id,
            repository=normalize_repository(repository),
            list_ids=tuple(sorted(observed_list_ids)),
            client_mutation_id=client_mutation_id,
        )

    def _graphql_write(
        self,
        query: str,
        *,
        raw_fields: dict[str, str],
        typed_fields: tuple[str, ...],
        operation: str,
    ) -> dict[str, Any]:
        self._tool_version = self._tool_version or self.check_environment()
        args = ["gh", "api", "graphql", "--raw-field", f"query={query}"]
        for key, value in sorted(raw_fields.items()):
            args.extend(("--raw-field", f"{key}={value}"))
        for value in typed_fields:
            args.extend(("--field", value))
        completed = self._run(tuple(args), operation=operation)
        if completed.returncode != 0:
            self._raise_api_failure("graphql", completed)
        if len(completed.stdout.encode("utf-8")) > MAX_API_RESPONSE_BYTES:
            raise GitHubSchemaError(
                code="github_response_too_large",
                message="GitHub mutation response exceeded its safety limit.",
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise GitHubSchemaError(
                code="github_invalid_json",
                message="GitHub mutation returned invalid JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise GitHubSchemaError(
                code="github_schema_mismatch",
                message="GitHub mutation response was not an object.",
            )
        errors = payload.get("errors")
        if errors:
            diagnostic = _redact(json.dumps(errors, ensure_ascii=False)[:500])
            lowered = diagnostic.casefold()
            if "rate limit" in lowered:
                raise GitHubRateLimitError(
                    code="github_rate_limited",
                    message="GitHub rate-limited the additive mutation.",
                )
            if "authentication" in lowered or "unauthorized" in lowered:
                raise GitHubAuthError(
                    code="github_auth_failed",
                    message="GitHub authentication failed during the additive mutation.",
                )
            raise GitHubSchemaError(
                code="github_graphql_error",
                message=f"GitHub rejected the additive mutation: {diagnostic}",
            )
        if not isinstance(payload.get("data"), dict):
            raise GitHubSchemaError(
                code="github_schema_mismatch",
                message="GitHub mutation response omitted its data object.",
            )
        return payload


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GitHubSchemaError(
            code="github_mutation_schema_invalid",
            message=f"GitHub {label} was not an object.",
        )
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise GitHubSchemaError(
            code="github_mutation_schema_invalid",
            message=f"GitHub {label} was not an array.",
        )
    return value
