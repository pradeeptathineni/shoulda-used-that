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
from shoulda_used_that.errors import StateError
from shoulda_used_that.models import (
    AdoptionPlan,
    CheckReceipt,
    DecisionReceipt,
    ProjectionPlan,
    RecheckReceipt,
    SavedItem,
    SaveReceipt,
)

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
