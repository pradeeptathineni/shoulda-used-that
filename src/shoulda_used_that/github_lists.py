"""Typed GitHub identity, star, List, and preview-capability reads."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import Field, field_validator, model_validator

from shoulda_used_that.canonical import digest
from shoulda_used_that.errors import (
    GitHubAuthError,
    GitHubError,
    GitHubSchemaError,
    StateError,
)
from shoulda_used_that.github import API_VERSION, GhAuthStatus, GhClient, GhResult
from shoulda_used_that.models import FrozenModel, normalize_repository, utc_now

MAX_GRAPHQL_PAGES = 100
REQUIRED_LIST_MUTATIONS = ("createUserList", "updateUserListsForItem")
REQUIRED_MUTATION_SCOPE = "user"
CAPABILITY_QUERY = """
query {
  viewer { login id }
  userType: __type(name: "User") { fields(includeDeprecated: true) { name } }
  itemType: __type(name: "UserListItems") { kind possibleTypes { name } }
  mutationType: __type(name: "Mutation") { fields { name } }
  createInput: __type(name: "CreateUserListInput") { inputFields { name } }
  membershipInput: __type(name: "UpdateUserListsForItemInput") { inputFields { name } }
}
"""
VIEWER_LISTS_QUERY = """
query($after: String) {
  viewer {
    login
    id
    lists(first: 100, after: $after) {
      totalCount
      nodes {
        id name description isPrivate slug
        items(first: 100) {
          totalCount
          nodes {
            __typename
            ... on Repository { id nameWithOwner isPrivate isArchived url }
          }
          pageInfo { hasNextPage endCursor }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""
USER_LISTS_QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    login
    id
    lists(first: 100, after: $after) {
      totalCount
      nodes {
        id name description isPrivate slug
        items(first: 100) {
          totalCount
          nodes {
            __typename
            ... on Repository { id nameWithOwner isPrivate isArchived url }
          }
          pageInfo { hasNextPage endCursor }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""
LIST_ITEMS_QUERY = """
query($id: ID!, $after: String) {
  node(id: $id) {
    __typename
    ... on UserList {
      items(first: 100, after: $after) {
        totalCount
        nodes {
          __typename
          ... on Repository { id nameWithOwner isPrivate isArchived url }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""


class GitHubCapabilityState(StrEnum):
    AVAILABLE = "available"
    MISSING_SCOPE = "missing_scope"
    PREVIEW_CHANGED = "preview_changed"
    UNAUTHENTICATED = "unauthenticated"
    UNAVAILABLE = "unavailable"


class GitHubCapabilityProbe(FrozenModel):
    observed_at: datetime
    state: GitHubCapabilityState
    login: str
    node_id: str | None = None
    host: Literal["github.com"] = "github.com"
    gh_version: str
    scopes: tuple[str, ...]
    rest_api_version: str
    rest_api_probe_passed: bool
    lists_field_present: bool
    repository_item_union_exact: bool
    required_mutations_present: bool
    required_mutations: tuple[str, ...] = REQUIRED_LIST_MUTATIONS
    missing_scopes: tuple[str, ...] = ()
    error_code: str | None = None
    operator_command: str | None = None

    @field_validator("scopes", "missing_scopes", mode="before")
    @classmethod
    def stable_scopes(cls, value: Any) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in value or () if str(item).strip()}))


class GitHubListMember(FrozenModel):
    node_id: str
    repository: str
    is_private: bool
    is_archived: bool
    url: str

    _normalize_repository = field_validator("repository")(normalize_repository)


class GitHubListState(FrozenModel):
    node_id: str
    name: str = Field(min_length=1)
    description: str | None = None
    is_private: bool
    slug: str
    members: tuple[GitHubListMember, ...]
    unknown_item_types: tuple[str, ...] = ()

    @field_validator("unknown_item_types", mode="before")
    @classmethod
    def stable_unknown_types(cls, value: Any) -> tuple[str, ...]:
        return tuple(sorted({str(item) for item in value or ()}))


class GitHubListCollection(FrozenModel):
    login: str
    node_id: str
    lists: tuple[GitHubListState, ...]


class StarredRepository(FrozenModel):
    node_id: str
    repository: str
    is_private: bool
    is_archived: bool
    url: str
    starred_at: datetime | None = None

    _normalize_repository = field_validator("repository")(normalize_repository)


class GitHubRelevantRepository(FrozenModel):
    node_id: str
    repository: str
    is_private: bool
    is_archived: bool
    url: str
    starred: bool
    starred_at: datetime | None = None

    _normalize_repository = field_validator("repository")(normalize_repository)


class GitHubCurationState(FrozenModel):
    account: str
    account_node_id: str
    observed_at: datetime
    total_starred_count: int = Field(ge=0)
    relevant_repositories: tuple[GitHubRelevantRepository, ...]
    lists: tuple[GitHubListState, ...]
    state_fingerprint: str = Field(pattern=r"^github_[0-9a-f]{64}$")

    @model_validator(mode="after")
    def fingerprint_matches_state(self) -> GitHubCurationState:
        repositories = [item.model_dump(mode="json") for item in self.relevant_repositories]
        lists = [item.model_dump(mode="json") for item in self.lists]
        semantic = {
            "account": self.account,
            "account_node_id": self.account_node_id,
            "relevant_repositories": repositories,
            "lists": lists,
        }
        if self.state_fingerprint != digest(semantic, prefix="github"):
            raise ValueError("GitHub state fingerprint does not match relevant state")
        return self


class GitHubReadClient(Protocol):
    def auth_status(self) -> GhAuthStatus: ...

    def graphql(
        self,
        query: str,
        *,
        variables: dict[str, str] | None = None,
        maximum_output_bytes: int = 20 * 1024 * 1024,
    ) -> GhResult: ...

    def api_version_probe(self) -> GhResult: ...

    def starred(self) -> GhResult: ...

    def user_starred(self, login: str) -> GhResult: ...

    def repository(self, repository: str) -> GhResult: ...


def probe_capabilities(
    client: GitHubReadClient | None = None, *, observed_at: datetime | None = None
) -> GitHubCapabilityProbe:
    """Probe exact identity, scope, REST, and GraphQL preview capabilities."""

    github = client or GhClient()
    timestamp = observed_at or utc_now()
    try:
        auth = github.auth_status()
    except GitHubAuthError as exc:
        return GitHubCapabilityProbe(
            observed_at=timestamp,
            state=GitHubCapabilityState.UNAUTHENTICATED,
            login="",
            gh_version="unavailable",
            scopes=(),
            rest_api_version=API_VERSION,
            rest_api_probe_passed=False,
            lists_field_present=False,
            repository_item_union_exact=False,
            required_mutations_present=False,
            error_code=exc.code,
        )
    base = {
        "observed_at": timestamp,
        "login": auth.login,
        "host": "github.com",
        "gh_version": auth.tool_version,
        "scopes": auth.scopes,
        "rest_api_version": API_VERSION,
    }
    rest_api_probe_passed = False
    try:
        rest_result = github.api_version_probe()
        if not isinstance(rest_result.payload, dict):
            raise GitHubSchemaError(
                code="github_api_version_probe_invalid",
                message="GitHub REST version probe did not return an object.",
            )
        rest_api_probe_passed = True
        result = github.graphql(CAPABILITY_QUERY)
        data = _mapping(_mapping(result.payload, "GraphQL response").get("data"), "data")
        viewer = _mapping(data.get("viewer"), "viewer")
        login = viewer.get("login")
        node_id = viewer.get("id")
        if not isinstance(login, str) or not isinstance(node_id, str):
            raise GitHubSchemaError(
                code="github_viewer_schema_invalid",
                message="GitHub viewer identity omitted login or node ID.",
            )
        if login.casefold() != auth.login.casefold():
            raise GitHubSchemaError(
                code="github_identity_mismatch",
                message="GitHub auth status and GraphQL viewer identity disagree.",
            )
        user_type = _mapping(data.get("userType"), "User introspection")
        user_fields = _list(user_type.get("fields"), "User fields")
        lists_field_present = any(
            isinstance(item, dict) and item.get("name") == "lists" for item in user_fields
        )
        item_type = _mapping(data.get("itemType"), "UserListItems introspection")
        possible_types = _list(item_type.get("possibleTypes"), "UserListItems types")
        item_names = {
            item.get("name")
            for item in possible_types
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        repository_item_union_exact = item_type.get("kind") == "UNION" and item_names == {
            "Repository"
        }
        mutation_type = _mapping(data.get("mutationType"), "Mutation introspection")
        mutation_fields = _list(mutation_type.get("fields"), "Mutation fields")
        mutation_names = {
            item.get("name")
            for item in mutation_fields
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        create_input = _mapping(data.get("createInput"), "CreateUserListInput introspection")
        create_fields = {
            item.get("name")
            for item in _list(create_input.get("inputFields"), "CreateUserListInput fields")
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        membership_input = _mapping(
            data.get("membershipInput"), "UpdateUserListsForItemInput introspection"
        )
        membership_fields = {
            item.get("name")
            for item in _list(
                membership_input.get("inputFields"),
                "UpdateUserListsForItemInput fields",
            )
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        required_mutations_present = (
            set(REQUIRED_LIST_MUTATIONS) <= mutation_names
            and {"name", "description", "isPrivate"} <= create_fields
            and {"itemId", "listIds"} <= membership_fields
        )
        preview_ok = (
            lists_field_present and repository_item_union_exact and required_mutations_present
        )
        missing_scopes = (
            () if REQUIRED_MUTATION_SCOPE in auth.scopes else (REQUIRED_MUTATION_SCOPE,)
        )
        state = (
            GitHubCapabilityState.PREVIEW_CHANGED
            if not preview_ok
            else GitHubCapabilityState.MISSING_SCOPE
            if missing_scopes
            else GitHubCapabilityState.AVAILABLE
        )
        return GitHubCapabilityProbe(
            **base,
            state=state,
            node_id=node_id,
            rest_api_probe_passed=True,
            lists_field_present=lists_field_present,
            repository_item_union_exact=repository_item_union_exact,
            required_mutations_present=required_mutations_present,
            missing_scopes=missing_scopes,
            operator_command=(
                "gh auth refresh --hostname github.com -s user" if missing_scopes else None
            ),
        )
    except GitHubError as exc:
        return GitHubCapabilityProbe(
            **base,
            state=GitHubCapabilityState.UNAVAILABLE,
            rest_api_probe_passed=rest_api_probe_passed,
            lists_field_present=False,
            repository_item_union_exact=False,
            required_mutations_present=False,
            error_code=exc.code,
        )


def read_user_lists(
    client: GitHubReadClient,
    *,
    login: str,
    viewer: bool,
) -> GitHubListCollection:
    """Read every visible List and item with complete cursor pagination."""

    lists: dict[str, GitHubListState] = {}
    after: str | None = None
    observed_login: str | None = None
    observed_node_id: str | None = None
    expected_total: int | None = None
    seen_cursors: set[str] = set()
    query = VIEWER_LISTS_QUERY if viewer else USER_LISTS_QUERY
    for _ in range(MAX_GRAPHQL_PAGES):
        variables = {"login": login} if not viewer else {}
        if after:
            variables["after"] = after
        result = client.graphql(query, variables=variables)
        data = _mapping(_mapping(result.payload, "GraphQL response").get("data"), "data")
        user_value = data.get("viewer" if viewer else "user")
        if user_value is None:
            raise GitHubSchemaError(
                code="github_user_not_found",
                message=f"GitHub user {login} was not found.",
            )
        user = _mapping(user_value, "List owner")
        page_login = user.get("login")
        page_node_id = user.get("id")
        if not isinstance(page_login, str) or not isinstance(page_node_id, str):
            raise GitHubSchemaError(
                code="github_lists_schema_invalid",
                message="GitHub List owner omitted login or node ID.",
            )
        if page_login.casefold() != login.casefold():
            raise GitHubSchemaError(
                code="github_identity_mismatch",
                message="GitHub List response belongs to a different account.",
            )
        if observed_login is not None and (
            page_login != observed_login or page_node_id != observed_node_id
        ):
            raise GitHubSchemaError(
                code="github_identity_drift",
                message="GitHub List owner changed during pagination.",
            )
        observed_login, observed_node_id = page_login, page_node_id
        connection = _mapping(user.get("lists"), "Lists connection")
        total_count = _integer(connection.get("totalCount"), "Lists totalCount")
        if expected_total is None:
            expected_total = total_count
        elif total_count != expected_total:
            raise GitHubSchemaError(
                code="github_pagination_drift",
                message="GitHub List count changed during pagination.",
            )
        for raw_list in _list(connection.get("nodes"), "List nodes"):
            parsed = _parse_list(client, raw_list)
            existing = lists.get(parsed.node_id)
            if existing is not None and existing != parsed:
                raise GitHubSchemaError(
                    code="github_list_duplicate_conflict",
                    message=f"GitHub returned conflicting pages for List {parsed.node_id}.",
                )
            lists[parsed.node_id] = parsed
        has_next, cursor = _page_info(connection.get("pageInfo"), "Lists")
        if not has_next:
            break
        if cursor is None or cursor in seen_cursors:
            raise GitHubSchemaError(
                code="github_pagination_invalid",
                message="GitHub Lists pagination repeated or omitted its cursor.",
            )
        seen_cursors.add(cursor)
        after = cursor
    else:
        raise GitHubSchemaError(
            code="github_pagination_limit",
            message="GitHub Lists exceeded the bounded pagination limit.",
        )
    if expected_total != len(lists):
        raise GitHubSchemaError(
            code="github_pagination_incomplete",
            message="GitHub Lists pagination did not return its declared total.",
        )
    if observed_login is None or observed_node_id is None:  # pragma: no cover - first page guard
        raise GitHubSchemaError(
            code="github_lists_schema_invalid",
            message="GitHub Lists response omitted its owner.",
        )
    return GitHubListCollection(
        login=observed_login,
        node_id=observed_node_id,
        lists=tuple(sorted(lists.values(), key=lambda item: (item.name.casefold(), item.node_id))),
    )


def read_starred(
    client: GitHubReadClient, *, login: str, viewer: bool
) -> tuple[StarredRepository, ...]:
    """Read authenticated timestamped stars or a user's public stars."""

    result = client.starred() if viewer else client.user_starred(login)
    items = _list(result.payload, "starred repositories")
    repositories: dict[str, StarredRepository] = {}
    for raw in items:
        if viewer:
            wrapper = _mapping(raw, "timestamped star")
            repository_payload = _mapping(wrapper.get("repo"), "starred repository")
            starred_at = wrapper.get("starred_at")
            if not isinstance(starred_at, str):
                raise GitHubSchemaError(
                    code="github_star_schema_invalid",
                    message="Authenticated star omitted starred_at.",
                )
        else:
            repository_payload = _mapping(raw, "public starred repository")
            starred_at = None
        repository = _repository_from_rest(repository_payload, starred_at=starred_at)
        existing = repositories.get(repository.repository)
        if existing is not None and existing != repository:
            raise GitHubSchemaError(
                code="github_star_duplicate_conflict",
                message=f"GitHub returned conflicting star data for {repository.repository}.",
            )
        repositories[repository.repository] = repository
    return tuple(repositories[key] for key in sorted(repositories))


def read_curation_state(
    client: GitHubReadClient,
    *,
    account: str,
    desired_repositories: tuple[str, ...],
    observed_at: datetime | None = None,
) -> GitHubCurationState:
    """Read only state material to one additive projection plan."""

    timestamp = observed_at or utc_now()
    stars = read_starred(client, login=account, viewer=True)
    lists = read_user_lists(client, login=account, viewer=True)
    if lists.login.casefold() != account.casefold():
        raise StateError(
            code="github_account_mismatch",
            message="Observed GitHub List owner does not match the requested account.",
        )
    starred_by_repository = {item.repository: item for item in stars}
    relevant: list[GitHubRelevantRepository] = []
    for raw_repository in sorted(set(desired_repositories)):
        repository = normalize_repository(raw_repository)
        starred = starred_by_repository.get(repository)
        if starred is not None:
            relevant.append(
                GitHubRelevantRepository(**starred.model_dump(mode="python"), starred=True)
            )
            continue
        result = client.repository(repository)
        observed = _repository_from_rest(
            _mapping(result.payload, "repository metadata"), starred_at=None
        )
        if observed.repository != repository:
            raise GitHubSchemaError(
                code="github_repository_identity_mismatch",
                message="GitHub repository metadata did not match the planned repository.",
            )
        relevant.append(
            GitHubRelevantRepository(**observed.model_dump(mode="python"), starred=False)
        )
    semantic = {
        "account": lists.login,
        "account_node_id": lists.node_id,
        "relevant_repositories": [item.model_dump(mode="json") for item in relevant],
        "lists": [item.model_dump(mode="json") for item in lists.lists],
    }
    return GitHubCurationState(
        account=lists.login,
        account_node_id=lists.node_id,
        observed_at=timestamp,
        total_starred_count=len(stars),
        relevant_repositories=tuple(relevant),
        lists=lists.lists,
        state_fingerprint=digest(semantic, prefix="github"),
    )


def _parse_list(client: GitHubReadClient, value: Any) -> GitHubListState:
    payload = _mapping(value, "UserList")
    node_id = payload.get("id")
    name = payload.get("name")
    description = payload.get("description")
    is_private = payload.get("isPrivate")
    slug = payload.get("slug")
    if (
        not isinstance(node_id, str)
        or not isinstance(name, str)
        or (description is not None and not isinstance(description, str))
        or not isinstance(is_private, bool)
        or not isinstance(slug, str)
    ):
        raise GitHubSchemaError(
            code="github_lists_schema_invalid",
            message="GitHub UserList omitted a required typed field.",
        )
    items = _mapping(payload.get("items"), "List items connection")
    expected_total = _integer(items.get("totalCount"), "List item totalCount")
    members, unknown = _parse_list_items(items.get("nodes"))
    has_next, cursor = _page_info(items.get("pageInfo"), "List items")
    seen_cursors: set[str] = set()
    for _ in range(MAX_GRAPHQL_PAGES):
        if not has_next:
            break
        if cursor is None or cursor in seen_cursors:
            raise GitHubSchemaError(
                code="github_pagination_invalid",
                message=f"GitHub List {name} repeated or omitted its item cursor.",
            )
        seen_cursors.add(cursor)
        result = client.graphql(LIST_ITEMS_QUERY, variables={"id": node_id, "after": cursor})
        data = _mapping(_mapping(result.payload, "GraphQL response").get("data"), "data")
        node = _mapping(data.get("node"), "UserList node")
        if node.get("__typename") != "UserList":
            raise GitHubSchemaError(
                code="github_lists_schema_invalid",
                message="GitHub List item page resolved to a different node type.",
            )
        connection = _mapping(node.get("items"), "List items connection")
        if _integer(connection.get("totalCount"), "List item totalCount") != expected_total:
            raise GitHubSchemaError(
                code="github_pagination_drift",
                message=f"GitHub List {name} changed during item pagination.",
            )
        page_members, page_unknown = _parse_list_items(connection.get("nodes"))
        members.extend(page_members)
        unknown.extend(page_unknown)
        has_next, cursor = _page_info(connection.get("pageInfo"), "List items")
    else:
        raise GitHubSchemaError(
            code="github_pagination_limit",
            message=f"GitHub List {name} exceeded the bounded item pagination limit.",
        )
    deduplicated: dict[str, GitHubListMember] = {}
    for member in members:
        existing = deduplicated.get(member.repository)
        if existing is not None and existing != member:
            raise GitHubSchemaError(
                code="github_list_item_duplicate_conflict",
                message=f"GitHub List {name} has conflicting repository items.",
            )
        deduplicated[member.repository] = member
    if expected_total != len(members) + len(unknown):
        raise GitHubSchemaError(
            code="github_pagination_incomplete",
            message=f"GitHub List {name} items did not match its declared total.",
        )
    return GitHubListState(
        node_id=node_id,
        name=name,
        description=description,
        is_private=is_private,
        slug=slug,
        members=tuple(deduplicated[key] for key in sorted(deduplicated)),
        unknown_item_types=tuple(unknown),
    )


def _parse_list_items(value: Any) -> tuple[list[GitHubListMember], list[str]]:
    members: list[GitHubListMember] = []
    unknown: list[str] = []
    for raw_item in _list(value, "List item nodes"):
        item = _mapping(raw_item, "List item")
        typename = item.get("__typename")
        if not isinstance(typename, str):
            raise GitHubSchemaError(
                code="github_lists_schema_invalid",
                message="GitHub List item omitted __typename.",
            )
        if typename != "Repository":
            unknown.append(typename)
            continue
        node_id = item.get("id")
        repository = item.get("nameWithOwner")
        is_private = item.get("isPrivate")
        is_archived = item.get("isArchived")
        url = item.get("url")
        if (
            not isinstance(node_id, str)
            or not isinstance(repository, str)
            or not isinstance(is_private, bool)
            or not isinstance(is_archived, bool)
            or not isinstance(url, str)
        ):
            raise GitHubSchemaError(
                code="github_lists_schema_invalid",
                message="GitHub repository List item omitted a required typed field.",
            )
        members.append(
            GitHubListMember(
                node_id=node_id,
                repository=repository,
                is_private=is_private,
                is_archived=is_archived,
                url=url,
            )
        )
    return members, unknown


def _repository_from_rest(payload: dict[str, Any], *, starred_at: str | None) -> StarredRepository:
    node_id = payload.get("node_id")
    repository = payload.get("full_name")
    is_private = payload.get("private")
    is_archived = payload.get("archived")
    url = payload.get("html_url")
    if (
        not isinstance(node_id, str)
        or not isinstance(repository, str)
        or not isinstance(is_private, bool)
        or not isinstance(is_archived, bool)
        or not isinstance(url, str)
    ):
        raise GitHubSchemaError(
            code="github_repository_schema_invalid",
            message="GitHub repository response omitted a required typed field.",
        )
    return StarredRepository(
        node_id=node_id,
        repository=repository,
        is_private=is_private,
        is_archived=is_archived,
        url=url,
        starred_at=starred_at,
    )


def _page_info(value: Any, label: str) -> tuple[bool, str | None]:
    page_info = _mapping(value, f"{label} pageInfo")
    has_next = page_info.get("hasNextPage")
    cursor = page_info.get("endCursor")
    if not isinstance(has_next, bool) or (cursor is not None and not isinstance(cursor, str)):
        raise GitHubSchemaError(
            code="github_pagination_invalid",
            message=f"GitHub {label} pageInfo was invalid.",
        )
    return has_next, cursor


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GitHubSchemaError(
            code="github_schema_mismatch", message=f"GitHub {label} was not an object."
        )
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise GitHubSchemaError(
            code="github_schema_mismatch", message=f"GitHub {label} was not an array."
        )
    return value


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GitHubSchemaError(
            code="github_schema_mismatch",
            message=f"GitHub {label} was not a non-negative integer.",
        )
    return value
