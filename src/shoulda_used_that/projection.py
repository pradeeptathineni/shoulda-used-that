"""Pure additive GitHub star/List projection planning."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field, model_validator

from shoulda_used_that.canonical import digest, short_id
from shoulda_used_that.curation import (
    CurationDisposition,
    CurationSnapshot,
    OperationCaps,
    validate_curation_snapshot,
)
from shoulda_used_that.errors import StateError
from shoulda_used_that.github_lists import (
    GitHubCapabilityProbe,
    GitHubCapabilityState,
    GitHubCurationState,
    GitHubListState,
)
from shoulda_used_that.models import FrozenModel, normalize_repository

PROJECTION_SCHEMA_VERSION: Literal["2.0"] = "2.0"
PROJECTABLE_DISPOSITIONS = frozenset(
    {
        CurationDisposition.ADOPT,
        CurationDisposition.TRIAL,
        CurationDisposition.REFERENCE,
        CurationDisposition.LEARN,
        CurationDisposition.BUILD,
    }
)
FORBIDDEN_OPERATION_CLASSES = (
    "change-list-privacy",
    "delete-list",
    "mutate-private-repository",
    "remove-list-membership",
    "rename-list",
    "replace-memberships",
    "unstar-repository",
)


class GitHubProjectionOperation(FrozenModel):
    operation_id: str = Field(pattern=r"^op_[0-9a-f]{24}$")
    kind: Literal["create-list", "star-repository", "add-membership"]
    collection_slug: str | None = None
    list_name: str | None = None
    list_description: str | None = None
    list_node_id: str | None = None
    repository: str | None = None
    repository_node_id: str | None = None
    preserved_list_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def fields_match_operation_kind(self) -> GitHubProjectionOperation:
        if self.kind == "create-list":
            if not all((self.collection_slug, self.list_name, self.list_description)):
                raise ValueError("create-list operation requires exact collection fields")
            if self.repository or self.repository_node_id or self.list_node_id:
                raise ValueError(
                    "create-list operation cannot target a repository or existing List"
                )
        elif self.kind == "star-repository":
            if not self.repository or not self.repository_node_id:
                raise ValueError("star-repository operation requires repository identity")
            if self.collection_slug or self.list_name or self.list_node_id:
                raise ValueError("star-repository operation cannot target a List")
        elif not all(
            (
                self.collection_slug,
                self.list_name,
                self.list_description,
                self.repository,
                self.repository_node_id,
            )
        ):
            raise ValueError("add-membership operation requires List and repository identity")
        return self


class ProjectedList(FrozenModel):
    collection_slug: str
    name: str
    description: str
    existing_node_id: str | None = None
    desired_repositories: tuple[str, ...]


class ProjectedRepository(FrozenModel):
    repository: str
    node_id: str
    was_starred: bool
    desired_collection_slugs: tuple[str, ...]
    preserved_existing_list_ids: tuple[str, ...]


class ProjectionExclusion(FrozenModel):
    repository: str
    collection_slug: str
    reason: str


class ProjectionOperationCounts(FrozenModel):
    create_lists: int = Field(ge=0)
    star_repositories: int = Field(ge=0)
    add_memberships: int = Field(ge=0)
    total: int = Field(ge=0)


class GitHubProjectionPlan(FrozenModel):
    schema_version: Literal["2.0"] = PROJECTION_SCHEMA_VERSION
    plan_id: str = Field(pattern=r"^gcp_[0-9a-f]{24}$")
    plan_kind: Literal["github-curation"] = "github-curation"
    created_at: datetime
    expires_at: datetime
    target_account: str
    observed_login: str
    observed_account_node_id: str
    source_curation_snapshot_id: str
    source_curation_fingerprint: str
    github_state_fingerprint: str
    github_state_observed_at: datetime
    capability: GitHubCapabilityProbe
    projected_lists: tuple[ProjectedList, ...]
    projected_repositories: tuple[ProjectedRepository, ...]
    operations: tuple[GitHubProjectionOperation, ...]
    exclusions: tuple[ProjectionExclusion, ...]
    forbidden_operation_classes: tuple[str, ...] = FORBIDDEN_OPERATION_CLASSES
    operation_counts: ProjectionOperationCounts
    caps: OperationCaps
    apply_ready: bool
    mutation_state: Literal["sealed-unapplied"] = "sealed-unapplied"
    canonical_plan_fingerprint: str = Field(pattern=r"^plan_[0-9a-f]{64}$")

    @model_validator(mode="after")
    def sealed_plan_is_coherent(self) -> GitHubProjectionPlan:
        if self.expires_at <= self.created_at:
            raise ValueError("projection plan expiry must be after creation")
        expected_counts = _operation_counts(self.operations)
        if self.operation_counts != expected_counts:
            raise ValueError("projection operation counts do not match operations")
        if set(self.forbidden_operation_classes) != set(FORBIDDEN_OPERATION_CLASSES):
            raise ValueError("projection plan must enumerate every forbidden operation class")
        if self.apply_ready and self.capability.state is not GitHubCapabilityState.AVAILABLE:
            raise ValueError("only an available capability probe can be apply-ready")
        semantic = self.model_dump(mode="json", exclude={"plan_id", "canonical_plan_fingerprint"})
        if self.canonical_plan_fingerprint != digest(semantic, prefix="plan"):
            raise ValueError("projection plan fingerprint does not match sealed content")
        if self.plan_id != short_id(semantic, prefix="gcp"):
            raise ValueError("projection plan ID does not match sealed content")
        return self


def build_projection_plan(
    snapshot: CurationSnapshot,
    state: GitHubCurationState,
    capability: GitHubCapabilityProbe,
    *,
    account: str,
    created_at: datetime,
) -> GitHubProjectionPlan:
    """Build one byte-stable additive-only plan from exact observed state."""

    validate_curation_snapshot(snapshot)
    policy = snapshot.projection_policy
    if not policy.enabled:
        raise StateError(
            code="github_projection_disabled",
            message="The curation profile has GitHub List projection disabled.",
        )
    if not policy.account or policy.account.casefold() != account.casefold():
        raise StateError(
            code="github_account_mismatch",
            message="Requested account does not match the curation profile's exact account.",
        )
    if (
        capability.login.casefold() != account.casefold()
        or state.account.casefold() != account.casefold()
    ):
        raise StateError(
            code="github_account_mismatch",
            message="Requested, authenticated, and observed GitHub accounts must match.",
        )
    if capability.node_id != state.account_node_id:
        raise StateError(
            code="github_account_identity_mismatch",
            message="Capability and state probes disagree on the GitHub account node identity.",
        )
    if capability.state not in {
        GitHubCapabilityState.AVAILABLE,
        GitHubCapabilityState.MISSING_SCOPE,
    }:
        raise StateError(
            code="github_capability_unavailable",
            message=f"GitHub Lists capability is {capability.state.value}; no plan was sealed.",
        )
    unknown_item_types = sorted(
        {item_type for github_list in state.lists for item_type in github_list.unknown_item_types}
    )
    if unknown_item_types:
        raise StateError(
            code="github_preview_changed",
            message="GitHub Lists returned an unknown item type; planning failed closed.",
            details={"item_types": unknown_item_types},
        )

    collections = {item.slug: item for item in snapshot.collection_definitions}
    selected = policy.selected_collection_slugs
    if len(selected) > policy.max_projected_lists:
        raise StateError(
            code="github_list_policy_exceeded",
            message="Selected collections exceed the profile's projected List cap.",
        )
    existing_by_name = _lists_by_name(state.lists)
    entries = {item.repository: item for item in snapshot.entries}
    desired_memberships: dict[str, set[str]] = {}
    exclusions: list[ProjectionExclusion] = []
    projected_lists: list[ProjectedList] = []
    for slug in selected:
        collection = collections.get(slug)
        if collection is None or not collection.github_list_projection:
            raise StateError(
                code="github_projection_collection_invalid",
                message=f"Selected collection {slug} is absent or not projection-enabled.",
            )
        if len(collection.title) > 32 or len(collection.description) > 160:
            raise StateError(
                code="github_list_text_too_long",
                message=f"Collection {slug} exceeds conservative GitHub List text limits.",
            )
        existing = existing_by_name.get(collection.title.casefold())
        if existing is not None and (
            existing.is_private or (existing.description or "") != collection.description
        ):
            raise StateError(
                code="github_list_conflict",
                message=(
                    f"GitHub List {collection.title!r} exists with different description "
                    "or visibility."
                ),
            )
        desired_repositories: list[str] = []
        for repository in snapshot.collection_membership_map.get(slug, ()):
            entry = entries.get(repository)
            if entry is None:
                raise StateError(
                    code="curation_snapshot_inconsistent",
                    message=f"Collection {slug} references missing entry {repository}.",
                )
            if entry.primary_disposition not in PROJECTABLE_DISPOSITIONS:
                exclusions.append(
                    ProjectionExclusion(
                        repository=repository,
                        collection_slug=slug,
                        reason=(
                            f"{entry.primary_disposition.value} is not projected to GitHub Lists"
                        ),
                    )
                )
                continue
            desired_memberships.setdefault(repository, set()).add(slug)
            desired_repositories.append(repository)
        projected_lists.append(
            ProjectedList(
                collection_slug=slug,
                name=collection.title,
                description=collection.description,
                existing_node_id=existing.node_id if existing else None,
                desired_repositories=tuple(sorted(set(desired_repositories))),
            )
        )

    repository_state = {item.repository: item for item in state.relevant_repositories}
    if set(repository_state) != set(desired_memberships):
        raise StateError(
            code="github_state_scope_mismatch",
            message="Observed GitHub repository scope does not match the desired projection.",
        )
    memberships_by_node = _memberships_by_repository_node(state.lists)
    projected_repositories: list[ProjectedRepository] = []
    for repository in sorted(desired_memberships):
        observed = repository_state[repository]
        if observed.is_private:
            raise StateError(
                code="github_private_repository_blocked",
                message=f"Private repository {repository} cannot enter a public projection.",
            )
        if observed.is_archived:
            raise StateError(
                code="github_archived_repository_blocked",
                message=f"Archived repository {repository} requires review before projection.",
            )
        preserved = memberships_by_node.get(observed.node_id, ())
        projected_repositories.append(
            ProjectedRepository(
                repository=repository,
                node_id=observed.node_id,
                was_starred=observed.starred,
                desired_collection_slugs=tuple(sorted(desired_memberships[repository])),
                preserved_existing_list_ids=preserved,
            )
        )

    operations: list[GitHubProjectionOperation] = []
    for projected_list in sorted(projected_lists, key=lambda item: item.collection_slug):
        if projected_list.existing_node_id is None:
            operations.append(
                _operation(
                    kind="create-list",
                    collection_slug=projected_list.collection_slug,
                    list_name=projected_list.name,
                    list_description=projected_list.description,
                )
            )
    for projected_repository in projected_repositories:
        if not projected_repository.was_starred:
            operations.append(
                _operation(
                    kind="star-repository",
                    repository=projected_repository.repository,
                    repository_node_id=projected_repository.node_id,
                )
            )
    projected_list_by_slug = {item.collection_slug: item for item in projected_lists}
    for projected_repository in projected_repositories:
        for slug in projected_repository.desired_collection_slugs:
            target = projected_list_by_slug[slug]
            if target.existing_node_id in projected_repository.preserved_existing_list_ids:
                continue
            operations.append(
                _operation(
                    kind="add-membership",
                    collection_slug=slug,
                    list_name=target.name,
                    list_description=target.description,
                    list_node_id=target.existing_node_id,
                    repository=projected_repository.repository,
                    repository_node_id=projected_repository.node_id,
                    preserved_list_ids=projected_repository.preserved_existing_list_ids,
                )
            )
    operations_tuple = tuple(operations)
    counts = _operation_counts(operations_tuple)
    _enforce_caps(counts, snapshot.mutation_policy.caps)
    semantic = {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "plan_kind": "github-curation",
        "created_at": _json_timestamp(created_at),
        "expires_at": _json_timestamp(
            created_at + timedelta(hours=snapshot.mutation_policy.plan_expiry_hours)
        ),
        "target_account": capability.login,
        "observed_login": capability.login,
        "observed_account_node_id": state.account_node_id,
        "source_curation_snapshot_id": snapshot.curation_snapshot_id,
        "source_curation_fingerprint": snapshot.canonical_fingerprint,
        "github_state_fingerprint": state.state_fingerprint,
        "github_state_observed_at": _json_timestamp(state.observed_at),
        "capability": capability.model_dump(mode="json"),
        "projected_lists": [item.model_dump(mode="json") for item in projected_lists],
        "projected_repositories": [item.model_dump(mode="json") for item in projected_repositories],
        "operations": [item.model_dump(mode="json") for item in operations_tuple],
        "exclusions": [item.model_dump(mode="json") for item in exclusions],
        "forbidden_operation_classes": list(FORBIDDEN_OPERATION_CLASSES),
        "operation_counts": counts.model_dump(mode="json"),
        "caps": snapshot.mutation_policy.caps.model_dump(mode="json"),
        "apply_ready": capability.state is GitHubCapabilityState.AVAILABLE,
        "mutation_state": "sealed-unapplied",
    }
    return GitHubProjectionPlan(
        plan_id=short_id(semantic, prefix="gcp"),
        created_at=created_at,
        expires_at=created_at + timedelta(hours=snapshot.mutation_policy.plan_expiry_hours),
        target_account=capability.login,
        observed_login=capability.login,
        observed_account_node_id=state.account_node_id,
        source_curation_snapshot_id=snapshot.curation_snapshot_id,
        source_curation_fingerprint=snapshot.canonical_fingerprint,
        github_state_fingerprint=state.state_fingerprint,
        github_state_observed_at=state.observed_at,
        capability=capability,
        projected_lists=tuple(projected_lists),
        projected_repositories=tuple(projected_repositories),
        operations=operations_tuple,
        exclusions=tuple(exclusions),
        operation_counts=counts,
        caps=snapshot.mutation_policy.caps,
        apply_ready=bool(semantic["apply_ready"]),
        canonical_plan_fingerprint=digest(semantic, prefix="plan"),
    )


def desired_projection_repositories(snapshot: CurationSnapshot) -> tuple[str, ...]:
    """Return normalized repositories needed for the selected public projection."""

    selected = set(snapshot.projection_policy.selected_collection_slugs)
    return tuple(
        sorted(
            {
                normalize_repository(entry.repository)
                for entry in snapshot.entries
                if entry.primary_disposition in PROJECTABLE_DISPOSITIONS
                and selected.intersection(entry.collection_memberships)
            }
        )
    )


def _operation(
    *,
    kind: Literal["create-list", "star-repository", "add-membership"],
    collection_slug: str | None = None,
    list_name: str | None = None,
    list_description: str | None = None,
    list_node_id: str | None = None,
    repository: str | None = None,
    repository_node_id: str | None = None,
    preserved_list_ids: tuple[str, ...] = (),
) -> GitHubProjectionOperation:
    semantic = {
        "kind": kind,
        "collection_slug": collection_slug,
        "list_name": list_name,
        "list_description": list_description,
        "list_node_id": list_node_id,
        "repository": repository,
        "repository_node_id": repository_node_id,
        "preserved_list_ids": list(preserved_list_ids),
    }
    return GitHubProjectionOperation(
        operation_id=short_id(semantic, prefix="op"),
        kind=kind,
        collection_slug=collection_slug,
        list_name=list_name,
        list_description=list_description,
        list_node_id=list_node_id,
        repository=repository,
        repository_node_id=repository_node_id,
        preserved_list_ids=preserved_list_ids,
    )


def _lists_by_name(lists: tuple[GitHubListState, ...]) -> dict[str, GitHubListState]:
    result: dict[str, GitHubListState] = {}
    for github_list in lists:
        key = github_list.name.casefold()
        if key in result:
            raise StateError(
                code="github_list_name_ambiguous",
                message=f"GitHub account has multiple Lists named {github_list.name!r}.",
            )
        result[key] = github_list
    return result


def _memberships_by_repository_node(
    lists: tuple[GitHubListState, ...],
) -> dict[str, tuple[str, ...]]:
    memberships: dict[str, set[str]] = {}
    for github_list in lists:
        for member in github_list.members:
            memberships.setdefault(member.node_id, set()).add(github_list.node_id)
    return {node_id: tuple(sorted(list_ids)) for node_id, list_ids in memberships.items()}


def _operation_counts(
    operations: tuple[GitHubProjectionOperation, ...],
) -> ProjectionOperationCounts:
    create_lists = sum(item.kind == "create-list" for item in operations)
    star_repositories = sum(item.kind == "star-repository" for item in operations)
    add_memberships = sum(item.kind == "add-membership" for item in operations)
    return ProjectionOperationCounts(
        create_lists=create_lists,
        star_repositories=star_repositories,
        add_memberships=add_memberships,
        total=len(operations),
    )


def _enforce_caps(counts: ProjectionOperationCounts, caps: OperationCaps) -> None:
    violations = {
        name: {"planned": planned, "cap": cap}
        for name, planned, cap in (
            ("total", counts.total, caps.total),
            ("create_lists", counts.create_lists, caps.create_lists),
            ("star_repositories", counts.star_repositories, caps.star_repositories),
            ("add_memberships", counts.add_memberships, caps.add_memberships),
        )
        if planned > cap
    }
    if violations:
        raise StateError(
            code="github_operation_cap_exceeded",
            message="GitHub projection exceeds one or more sealed operation caps.",
            details={"violations": violations},
        )


def _json_timestamp(value: datetime) -> str:
    rendered = value.isoformat()
    return f"{rendered.removesuffix('+00:00')}Z" if rendered.endswith("+00:00") else rendered
