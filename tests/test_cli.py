from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

from shoulda_used_that.cli import cli


def _checked_args(state: Path, fixture: Path, output_format: str = "json") -> list[str]:
    return [
        "--state-dir",
        str(state),
        "--format",
        output_format,
        "check",
        "find reusable receipt machinery",
        "--source",
        "fixture",
        "--fixture",
        str(fixture),
        "--language",
        "Python",
        "--license",
        "Apache-2.0",
        "--not-archived",
        "--maintained-within",
        "52w",
        "--sort",
        "-stars",
        "--explain-filter",
    ]


def test_checked_json_and_followup_chain(tmp_path: Path, fixture_path: Path) -> None:
    runner = CliRunner()
    state = tmp_path / "state"
    check_result = runner.invoke(cli, _checked_args(state, fixture_path))
    assert check_result.exit_code == 0, check_result.output
    check = json.loads(check_result.stdout)
    assert check["result_repositories"] == ["fixture-labs/canonical-kit"]
    check_id = check["check_id"]

    decision_result = runner.invoke(
        cli,
        [
            "--state-dir",
            str(state),
            "--format",
            "json",
            "remember",
            "fixture-labs/canonical-kit",
            "--as",
            "adopt",
            "--for",
            "canonical bytes",
            "--because",
            "verified fixture evidence",
            "--reconsider-when",
            "evidence changes",
            "--from",
            check_id,
        ],
    )
    assert decision_result.exit_code == 0, decision_result.output
    decision = json.loads(decision_result.stdout)
    assert decision["source_check_id"] == check_id

    recheck_result = runner.invoke(
        cli,
        ["--state-dir", str(state), "--format", "json", "recheck", check_id],
    )
    assert recheck_result.exit_code == 0, recheck_result.output
    assert json.loads(recheck_result.stdout)["outcome"] == "semantic-no-op"


@pytest.mark.parametrize("output_format", ["table", "yaml", "markdown"])
def test_human_and_view_outputs_are_uncolored_and_parseable(
    tmp_path: Path, fixture_path: Path, output_format: str
) -> None:
    result = CliRunner().invoke(
        cli, _checked_args(tmp_path / output_format, fixture_path, output_format)
    )
    assert result.exit_code == 0, result.output
    assert "\x1b[" not in result.stdout
    if output_format == "yaml":
        assert yaml.safe_load(result.stdout)["schema_version"] == "1.0"
    elif output_format == "markdown":
        assert result.stdout.startswith("# CheckReceipt\n")
    else:
        assert "fixture-labs/canonical-kit" in result.stdout


def test_default_check_output_is_bounded_answer_first_and_diagnostic(
    tmp_path: Path, fixture_path: Path
) -> None:
    runner = CliRunner()
    base = [
        "--state-dir",
        str(tmp_path / "state"),
        "check",
        "canonical identity",
        "--source",
        "fixture",
        "--fixture",
        str(fixture_path),
    ]
    result = runner.invoke(
        cli,
        [*base, "--language", "Python", "--license", "Apache-2.0", "--not-archived"],
    )
    assert result.exit_code == 0, result.output
    assert "fixture-labs/canonical-kit" in result.stdout
    assert "fixture-labs/query-needle" not in result.stdout
    assert "Filtered or gated: 4" in result.stdout
    assert "Result fingerprint" not in result.stdout
    assert "NEED is context only and never expands a query" in result.stdout
    assert "fixture input #1" in result.stdout
    assert "fixture:src_" not in result.stdout
    assert len(result.stdout.splitlines()) <= 30

    empty = runner.invoke(cli, [*base, "--language", "Rust"])
    assert empty.exit_code == 0, empty.output
    assert "Zero-result diagnosis" in empty.stdout
    assert "every source candidate was removed" in empty.stdout
    assert "nothing was broadened" in empty.stdout


def test_retired_and_replaced_commands_are_absent() -> None:
    runner = CliRunner()
    for command in (
        "saved",
        "used",
        "checked",
        "inspected",
        "remembered",
        "rechecked",
        "curated",
        "exported",
        "projected",
        "apply",
        "verify",
    ):
        result = runner.invoke(cli, [command])
        assert result.exit_code == 2
        assert f"No such command '{command}'" in result.output


def test_catalog_and_github_commands_are_discoverable_groups(tmp_path: Path) -> None:
    runner = CliRunner()
    help_result = runner.invoke(cli, ["--help"])
    catalog_help = runner.invoke(cli, ["catalog", "--help"])
    github_help = runner.invoke(cli, ["github", "--help"])
    version = runner.invoke(cli, ["--version"])
    assert help_result.exit_code == 0, help_result.output
    assert version.stdout == "shoulda, version 0.4.0\n"
    for command in ("catalog", "check", "github", "inspect", "recheck", "remember"):
        assert command in help_result.stdout
    for command in ("build", "export"):
        assert command in catalog_help.stdout
    for command in ("plan", "apply", "verify"):
        assert command in github_help.stdout
    for retired_command in ("saved", "used", "--admin"):
        assert retired_command not in help_result.stdout

    invalid = runner.invoke(
        cli,
        [
            "--state-dir",
            str(tmp_path / "state"),
            "--format",
            "json",
            "github",
            "verify",
            "app_example",
        ],
    )
    assert invalid.exit_code == 2
    assert json.loads(invalid.stderr)["error"]["code"] == "invalid_identifier"


def test_importing_cli_does_not_eagerly_load_operational_modules() -> None:
    command = """
import json
import sys
import shoulda_used_that.cli

blocked = {
    'shoulda_used_that.admin_services',
    'shoulda_used_that.curation',
    'shoulda_used_that.github_apply',
    'shoulda_used_that.github_mutations',
    'shoulda_used_that.projection',
    'shoulda_used_that.public_export',
}
print(json.dumps(sorted(blocked.intersection(sys.modules))))
"""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and static script
        [sys.executable, "-c", command],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == []


def test_github_action_commands_report_complete_and_incomplete_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from shoulda_used_that import admin_services

    applied_calls: list[dict[str, Any]] = []

    def fake_applied(_store: Any, **kwargs: Any) -> SimpleNamespace:
        applied_calls.append(kwargs)
        status = "complete" if kwargs["plan_id"] == "gcp_complete" else "partial"
        return SimpleNamespace(kind="apply", status=SimpleNamespace(value=status))

    def fake_verified(_store: Any, *, apply_receipt_id: str) -> SimpleNamespace:
        status = "verified" if apply_receipt_id == "app_verified" else "mismatch"
        return SimpleNamespace(kind="verify", status=SimpleNamespace(value=status))

    monkeypatch.setattr(admin_services, "applied", fake_applied)
    monkeypatch.setattr(admin_services, "verified", fake_verified)
    monkeypatch.setattr(
        "shoulda_used_that.cli.render",
        lambda value, _output_format: f"{value.kind}:{value.status.value}\n",
    )
    base = ["--state-dir", str(tmp_path / "state"), "github"]
    runner = CliRunner()

    complete = runner.invoke(
        cli,
        [*base, "apply", "gcp_complete", "--fingerprint", "plan_complete"],
    )
    partial = runner.invoke(
        cli,
        [*base, "apply", "gcp_partial", "--fingerprint", "plan_partial"],
    )
    verified = runner.invoke(cli, [*base, "verify", "app_verified"])
    mismatch = runner.invoke(cli, [*base, "verify", "app_mismatch"])

    assert (complete.exit_code, complete.stdout) == (0, "apply:complete\n")
    assert (partial.exit_code, partial.stdout) == (2, "apply:partial\n")
    assert (verified.exit_code, verified.stdout) == (0, "verify:verified\n")
    assert (mismatch.exit_code, mismatch.stdout) == (2, "verify:mismatch\n")
    assert [call["fingerprint"] for call in applied_calls] == [
        "plan_complete",
        "plan_partial",
    ]
    assert all(call["environment"] is not None for call in applied_calls)
    assert all(call["stdin_isatty"] is False for call in applied_calls)


@pytest.mark.parametrize(
    ("extra", "code"),
    [
        (["--fixture", "unused.json"], "unused_fixture"),
        (["--query", "unused"], "unused_query"),
        (["--repo", "fixture-labs/unused"], "unused_repo"),
    ],
)
def test_unused_source_arguments_are_typed_errors(
    tmp_path: Path, extra: list[str], code: str
) -> None:
    result = CliRunner().invoke(
        cli,
        [
            "--state-dir",
            str(tmp_path / "state"),
            "--format",
            "json",
            "check",
            "test",
            "--source",
            "stars",
            *extra,
        ],
    )
    assert result.exit_code == 2
    assert json.loads(result.stderr)["error"]["code"] == code


@pytest.mark.parametrize(
    ("source", "code"),
    [
        ("fixture", "fixture_required"),
        ("github-search", "query_required"),
        ("repository", "repository_required"),
    ],
)
def test_selected_sources_require_locators(tmp_path: Path, source: str, code: str) -> None:
    result = CliRunner().invoke(
        cli,
        [
            "--state-dir",
            str(tmp_path / "state"),
            "--format",
            "json",
            "check",
            "test",
            "--source",
            source,
        ],
    )

    assert result.exit_code == 2
    assert json.loads(result.stderr)["error"]["code"] == code


def test_invalid_duration_and_input_have_machine_error(tmp_path: Path, fixture_path: Path) -> None:
    args = _checked_args(tmp_path / "state", fixture_path)
    index = args.index("52w")
    args[index] = "one year"
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 2
    error = json.loads(result.stderr)["error"]
    assert error["code"] == "invalid_input"
    assert "365d or 12w" in error["message"]


def test_version_and_help_expose_stable_surface() -> None:
    runner = CliRunner()
    version = runner.invoke(cli, ["--version"])
    help_result = runner.invoke(cli, ["--help"])
    checked_help = runner.invoke(cli, ["check", "--help"])
    assert version.exit_code == 0
    assert version.stdout == "shoulda, version 0.4.0\n"
    assert help_result.exit_code == 0
    assert "Start here: check finds options" in help_result.stdout
    assert "Find candidates from an explicit source/query plan" in help_result.stdout
    for command in ("check", "inspect", "remember", "recheck"):
        assert command in help_result.stdout
    for hidden in ("curated", "exported", "projected", "saved", "used"):
        assert hidden not in help_result.stdout
    for nested in ("apply", "verify"):
        assert f"\n  {nested} " not in help_result.stdout
    assert checked_help.exit_code == 0
    assert "Explicit discovery source" in checked_help.stdout
    assert "NEED never expands or rewrites it" in " ".join(checked_help.stdout.split())
    assert "Show candidate-level filter and limit reasons" in checked_help.stdout
    assert "default: 5" in checked_help.stdout
