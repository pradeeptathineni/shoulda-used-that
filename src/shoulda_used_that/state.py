"""Profile-scoped, content-safe local file state outside target repositories."""

from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import TypeVar

from platformdirs import user_data_path
from pydantic import BaseModel, ValidationError

from shoulda_used_that.canonical import canonical_bytes, digest
from shoulda_used_that.curation import CurationSnapshot
from shoulda_used_that.errors import StateError
from shoulda_used_that.github_apply import (
    ApplyOperationReceipt,
    ApplyReceipt,
    VerifyReceipt,
)
from shoulda_used_that.github_lists import GitHubCurationState
from shoulda_used_that.models import (
    AdoptionPlan,
    CheckReceipt,
    DecisionReceipt,
    ProjectionPlan,
    RecheckReceipt,
    SavedItem,
    SaveReceipt,
)
from shoulda_used_that.project_context import ProjectSnapshot
from shoulda_used_that.projection import GitHubProjectionPlan

PROFILE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
ModelT = TypeVar("ModelT", bound=BaseModel)


def default_state_root() -> Path:
    """Return the OS-appropriate private data directory."""

    return user_data_path("shoulda-used-that", "ShouldaUsedThat", ensure_exists=False)


class StateStore:
    """Write immutable receipts and small mutable profile pointers atomically."""

    def __init__(self, root: Path | None = None, *, profile: str = "default") -> None:
        if not PROFILE_PATTERN.fullmatch(profile):
            raise StateError(
                code="invalid_profile",
                message=(
                    "Profile must start with an alphanumeric character and contain only "
                    "letters, digits, '.', '_', or '-'."
                ),
                details={"profile": profile},
            )
        selected = (root or default_state_root()).expanduser()
        if selected.exists() and selected.is_symlink():
            raise StateError(
                code="unsafe_state_root",
                message=f"State root must not be a symlink: {selected}",
            )
        self.root = selected.resolve(strict=False)
        self.profile = profile
        self.profile_root = self.root / "profiles" / profile

    def initialize(self) -> None:
        for path in (
            self.root,
            self.profile_root,
            self.profile_root / "checks",
            self.profile_root / "saved" / "items",
            self.profile_root / "saved" / "receipts",
            self.profile_root / "decisions",
            self.profile_root / "rechecks",
            self.profile_root / "baselines",
            self.profile_root / "plans" / "projections",
            self.profile_root / "plans" / "adoptions",
            self.profile_root / "plans" / "github-curation",
            self.profile_root / "github-states",
            self.profile_root / "applies" / "operations",
            self.profile_root / "applies" / "latest",
            self.profile_root / "verifications",
            self.profile_root / "curations",
            self.profile_root / "curations" / "latest",
            self.profile_root / "projects",
            self.profile_root / "projects" / "latest",
        ):
            self._mkdir(path)

    def write_check(self, receipt: CheckReceipt) -> bool:
        self.initialize()
        created = self._write_immutable(self._path("checks", f"{receipt.check_id}.json"), receipt)
        self._write_pointer(
            self._path("latest-check.json"),
            {
                "check_id": receipt.check_id,
                "result_set_fingerprint": receipt.result_set_fingerprint,
            },
        )
        return created

    def write_check_snapshot(self, receipt: CheckReceipt) -> bool:
        """Store a revalidation snapshot without changing saved --all scope."""

        self.initialize()
        return self._write_immutable(self._path("checks", f"{receipt.check_id}.json"), receipt)

    def read_check(self, check_id: str) -> CheckReceipt:
        return self._read_model(self._path("checks", f"{_safe_id(check_id)}.json"), CheckReceipt)

    def latest_check(self) -> CheckReceipt:
        pointer = self._read_json(self._path("latest-check.json"))
        check_id = pointer.get("check_id")
        if not isinstance(check_id, str):
            raise StateError(
                code="latest_check_invalid",
                message="The latest-check pointer is invalid; run 'shoulda checked' again.",
            )
        return self.read_check(check_id)

    def write_saved_item(self, item: SavedItem) -> bool:
        self.initialize()
        item_name = digest(item.repository, prefix="repo")
        return self._write_immutable(self._path("saved", "items", f"{item_name}.json"), item)

    def saved_item(self, repository: str) -> SavedItem | None:
        item_name = digest(repository.lower(), prefix="repo")
        path = self._path("saved", "items", f"{item_name}.json")
        return None if not path.exists() else self._read_model(path, SavedItem)

    def write_save_receipt(self, receipt: SaveReceipt) -> bool:
        self.initialize()
        return self._write_immutable(
            self._path("saved", "receipts", f"{receipt.save_id}.json"), receipt
        )

    def write_decision(self, receipt: DecisionReceipt) -> bool:
        self.initialize()
        if receipt.supersedes:
            self.read_decision(receipt.supersedes)
        return self._write_immutable(
            self._path("decisions", f"{receipt.decision_id}.json"), receipt
        )

    def read_decision(self, decision_id: str) -> DecisionReceipt:
        return self._read_model(
            self._path("decisions", f"{_safe_id(decision_id)}.json"), DecisionReceipt
        )

    def write_recheck(self, receipt: RecheckReceipt) -> bool:
        self.initialize()
        return self._write_immutable(self._path("rechecks", f"{receipt.recheck_id}.json"), receipt)

    def write_projection(self, plan: ProjectionPlan) -> bool:
        self.initialize()
        return self._write_immutable(
            self._path("plans", "projections", f"{plan.plan_id}.json"), plan
        )

    def read_projection(self, plan_id: str) -> ProjectionPlan:
        return self._read_model(
            self._path("plans", "projections", f"{_safe_id(plan_id)}.json"),
            ProjectionPlan,
        )

    def write_adoption(self, plan: AdoptionPlan) -> bool:
        self.initialize()
        return self._write_immutable(self._path("plans", "adoptions", f"{plan.plan_id}.json"), plan)

    def read_adoption(self, plan_id: str) -> AdoptionPlan:
        return self._read_model(
            self._path("plans", "adoptions", f"{_safe_id(plan_id)}.json"), AdoptionPlan
        )

    def write_github_projection(self, plan: GitHubProjectionPlan) -> bool:
        self.initialize()
        return self._write_immutable(
            self._path("plans", "github-curation", f"{plan.plan_id}.json"), plan
        )

    def read_github_projection(self, plan_id: str) -> GitHubProjectionPlan:
        return self._read_model(
            self._path("plans", "github-curation", f"{_safe_id(plan_id)}.json"),
            GitHubProjectionPlan,
        )

    def write_github_state(self, state: GitHubCurationState) -> bool:
        self.initialize()
        path = self._path("github-states", f"{state.state_fingerprint}.json")
        if path.exists():
            # observed_at is intentionally excluded from the material state
            # fingerprint. Preserve the first immutable observation when a
            # later read is a semantic no-op.
            self._read_model(path, GitHubCurationState)
            return False
        return self._write_immutable(path, state)

    def read_github_state(self, state_fingerprint: str) -> GitHubCurationState:
        return self._read_model(
            self._path("github-states", f"{_safe_id(state_fingerprint)}.json"),
            GitHubCurationState,
        )

    def write_apply_operation(self, receipt: ApplyOperationReceipt) -> bool:
        self.initialize()
        return self._write_immutable(
            self._path("applies", "operations", f"{receipt.operation_receipt_id}.json"),
            receipt,
        )

    def write_apply(self, receipt: ApplyReceipt) -> bool:
        self.initialize()
        created = self._write_immutable(
            self._path("applies", f"{receipt.apply_receipt_id}.json"), receipt
        )
        self._write_pointer(
            self._latest_apply_path(receipt.plan_id),
            {
                "plan_id": receipt.plan_id,
                "apply_receipt_id": receipt.apply_receipt_id,
                "canonical_fingerprint": receipt.canonical_fingerprint,
            },
        )
        return created

    def read_apply(self, apply_receipt_id: str) -> ApplyReceipt:
        return self._read_model(
            self._path("applies", f"{_safe_id(apply_receipt_id)}.json"),
            ApplyReceipt,
        )

    def latest_apply(self, plan_id: str) -> ApplyReceipt | None:
        pointer_path = self._latest_apply_path(plan_id)
        if not pointer_path.exists():
            return None
        pointer = self._read_json(pointer_path)
        if pointer.get("plan_id") != plan_id:
            raise StateError(
                code="latest_apply_invalid",
                message="The plan-specific apply pointer has the wrong plan identity.",
            )
        apply_receipt_id = pointer.get("apply_receipt_id")
        if not isinstance(apply_receipt_id, str):
            raise StateError(
                code="latest_apply_invalid",
                message="The latest apply pointer is invalid.",
            )
        return self.read_apply(apply_receipt_id)

    def _latest_apply_path(self, plan_id: str) -> Path:
        plan_identity = digest(_safe_id(plan_id), prefix="plan")
        return self._path("applies", "latest", f"{plan_identity}.json")

    def write_verify(self, receipt: VerifyReceipt) -> bool:
        self.initialize()
        return self._write_immutable(
            self._path("verifications", f"{receipt.verify_receipt_id}.json"), receipt
        )

    def read_verify(self, verify_receipt_id: str) -> VerifyReceipt:
        return self._read_model(
            self._path("verifications", f"{_safe_id(verify_receipt_id)}.json"),
            VerifyReceipt,
        )

    def write_curation(self, snapshot: CurationSnapshot) -> bool:
        self.initialize()
        created = self._write_immutable(
            self._path("curations", f"{snapshot.curation_snapshot_id}.json"), snapshot
        )
        self._write_pointer(
            self._path("latest-curation.json"),
            {
                "profile_id": snapshot.profile_id,
                "curation_snapshot_id": snapshot.curation_snapshot_id,
                "canonical_fingerprint": snapshot.canonical_fingerprint,
            },
        )
        self._write_pointer(
            self._curation_pointer_path(snapshot.profile_id),
            {
                "profile_id": snapshot.profile_id,
                "curation_snapshot_id": snapshot.curation_snapshot_id,
                "canonical_fingerprint": snapshot.canonical_fingerprint,
            },
        )
        return created

    def read_curation(self, snapshot_id: str) -> CurationSnapshot:
        return self._read_model(
            self._path("curations", f"{_safe_id(snapshot_id)}.json"), CurationSnapshot
        )

    def latest_curation(self, profile_id: str | None = None) -> CurationSnapshot | None:
        pointer_path = (
            self._curation_pointer_path(profile_id)
            if profile_id is not None
            else self._path("latest-curation.json")
        )
        if not pointer_path.exists():
            return None
        pointer = self._read_json(pointer_path)
        if profile_id is not None and pointer.get("profile_id") != profile_id:
            raise StateError(
                code="latest_curation_invalid",
                message="The profile-specific curation pointer has the wrong profile identity.",
            )
        snapshot_id = pointer.get("curation_snapshot_id")
        if not isinstance(snapshot_id, str):
            raise StateError(
                code="latest_curation_invalid",
                message="The latest-curation pointer is invalid; run 'shoulda curated' again.",
            )
        return self.read_curation(snapshot_id)

    def _curation_pointer_path(self, profile_id: str) -> Path:
        pointer_id = digest(profile_id, prefix="profile")
        return self._path("curations", "latest", f"{pointer_id}.json")

    def write_project(self, snapshot: ProjectSnapshot) -> bool:
        self.initialize()
        created = self._write_immutable(
            self._path("projects", f"{snapshot.project_snapshot_id}.json"), snapshot
        )
        pointer = {
            "project_snapshot_id": snapshot.project_snapshot_id,
            "target_identity": snapshot.target_identity,
            "canonical_fingerprint": snapshot.canonical_fingerprint,
        }
        self._write_pointer(self._path("latest-project.json"), pointer)
        identity = digest(snapshot.target_identity, prefix="target")
        self._write_pointer(self._path("projects", "latest", f"{identity}.json"), pointer)
        return created

    def read_project(self, snapshot_id: str) -> ProjectSnapshot:
        return self._read_model(
            self._path("projects", f"{_safe_id(snapshot_id)}.json"), ProjectSnapshot
        )

    def latest_project(self, target_identity: str | None = None) -> ProjectSnapshot | None:
        if target_identity is None:
            pointer_path = self._path("latest-project.json")
        else:
            identity = digest(target_identity, prefix="target")
            pointer_path = self._path("projects", "latest", f"{identity}.json")
        if not pointer_path.exists():
            return None
        pointer = self._read_json(pointer_path)
        if target_identity is not None and pointer.get("target_identity") != target_identity:
            raise StateError(
                code="latest_project_invalid",
                message="The project pointer has the wrong target identity.",
            )
        snapshot_id = pointer.get("project_snapshot_id")
        if not isinstance(snapshot_id, str):
            raise StateError(
                code="latest_project_invalid",
                message="The latest-project pointer is invalid; run 'shoulda inspected' again.",
            )
        return self.read_project(snapshot_id)

    def resolve_check_for_target(self, target_id: str) -> tuple[CheckReceipt, str]:
        baseline_path = self._path("baselines", f"{_safe_id(target_id)}.json")
        if baseline_path.exists():
            pointer = self._read_json(baseline_path)
            baseline_id = pointer.get("check_id")
            if isinstance(baseline_id, str):
                return self.read_check(baseline_id), target_id
        if target_id.startswith("chk_"):
            return self.read_check(target_id), target_id
        if target_id.startswith("dec_"):
            decision = self.read_decision(target_id)
            if not decision.source_check_id:
                raise StateError(
                    code="decision_has_no_check",
                    message=(
                        f"Decision {target_id} is not bound to a check and cannot be "
                        "revalidated automatically."
                    ),
                )
            return self.read_check(decision.source_check_id), target_id
        raise StateError(
            code="unsupported_recheck_target",
            message="Recheck target must be a chk_ or dec_ identifier.",
            details={"target_id": target_id},
        )

    def update_baseline(self, target_id: str, check_id: str) -> None:
        self.initialize()
        self._write_pointer(
            self._path("baselines", f"{_safe_id(target_id)}.json"),
            {"target_id": target_id, "check_id": check_id},
        )

    def _path(self, *parts: str) -> Path:
        path = self.profile_root.joinpath(*parts)
        try:
            path.resolve(strict=False).relative_to(self.root)
        except ValueError as exc:
            raise StateError(
                code="unsafe_state_path",
                message="State path escaped the configured state root.",
            ) from exc
        return path

    def _mkdir(self, path: Path) -> None:
        try:
            path.resolve(strict=False).relative_to(self.root)
        except ValueError as exc:
            raise StateError(code="unsafe_state_path", message="Unsafe state directory.") from exc
        if path.exists() and path.is_symlink():
            raise StateError(
                code="unsafe_state_path",
                message=f"State directory must not be a symlink: {path}",
            )
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        with suppress(OSError):
            path.chmod(0o700)

    def _write_immutable(self, path: Path, model: BaseModel) -> bool:
        payload = canonical_bytes(model.model_dump(mode="json")) + b"\n"
        if path.exists():
            if path.is_symlink():
                raise StateError(
                    code="unsafe_state_path", message=f"Receipt path must not be a symlink: {path}"
                )
            existing = path.read_bytes()
            if existing == payload:
                return False
            raise StateError(
                code="immutable_receipt_conflict",
                message=f"Receipt {path.name} already exists with different content.",
            )
        self._atomic_write(path, payload)
        return True

    def _write_pointer(self, path: Path, value: dict[str, str]) -> None:
        self._atomic_write(path, canonical_bytes(value) + b"\n")

    def _atomic_write(self, path: Path, payload: bytes) -> None:
        self._mkdir(path.parent)
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        try:
            temporary_path.chmod(0o600)
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _read_model(self, path: Path, model: type[ModelT]) -> ModelT:
        payload = self._read_json(path)
        try:
            return model.model_validate(payload)
        except ValidationError as exc:
            raise StateError(
                code="state_schema_invalid",
                message=f"State file {path.name} does not match {model.__name__}: {exc}",
            ) from exc

    def _read_json(self, path: Path) -> dict[str, object]:
        if not path.exists():
            raise StateError(
                code="state_not_found",
                message=f"Required state was not found: {path.name}",
                details={"path": str(path)},
            )
        if path.is_symlink() or not path.is_file():
            raise StateError(
                code="unsafe_state_path",
                message=f"State must be a regular non-symlink file: {path}",
            )
        try:
            value = json.loads(path.read_bytes())
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise StateError(
                code="state_unreadable",
                message=f"State file is unreadable: {path.name}: {exc}",
            ) from exc
        if not isinstance(value, dict):
            raise StateError(
                code="state_schema_invalid",
                message=f"State file must contain a JSON object: {path.name}",
            )
        return value


def _safe_id(value: str) -> str:
    if not re.fullmatch(r"[a-z]+_[a-f0-9]{16,64}", value):
        raise StateError(
            code="invalid_identifier",
            message=f"Invalid receipt identifier: {value}",
        )
    return value
