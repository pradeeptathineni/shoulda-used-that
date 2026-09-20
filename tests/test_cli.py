from __future__ import annotations

import json
from pathlib import Path

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
        "checked",
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

    save_result = runner.invoke(
        cli,
        [
            "--state-dir",
            str(state),
            "--format",
            "json",
            "saved",
            "--all",
            "--from",
            check_id,
        ],
    )
    assert save_result.exit_code == 0, save_result.output
    assert json.loads(save_result.stdout)["created"] == ["fixture-labs/canonical-kit"]

    decision_result = runner.invoke(
        cli,
        [
            "--state-dir",
            str(state),
            "--format",
            "json",
            "remembered",
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
        ["--state-dir", str(state), "--format", "json", "rechecked", check_id],
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
        "checked",
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
    assert "fixture:candidates.json #1" in result.stdout
    assert len(result.stdout.splitlines()) <= 30

    empty = runner.invoke(cli, [*base, "--language", "Rust"])
    assert empty.exit_code == 0, empty.output
    assert "Zero-result diagnosis" in empty.stdout
    assert "every source candidate was removed" in empty.stdout
    assert "nothing was broadened" in empty.stdout


def test_used_then_apply_and_verify_fail_closed(tmp_path: Path) -> None:
    runner = CliRunner()
    state = tmp_path / "state"
    used_result = runner.invoke(
        cli,
        [
            "--state-dir",
            str(state),
            "--format",
            "json",
            "used",
            "fixture-labs/canonical-kit",
            "--for",
            "canonical bytes",
            "--in",
            "synthetic-target",
            "--file",
            "adapter.py",
            "--tool",
            "pytest",
            "--test",
            "published vectors",
            "--postcondition",
            "vectors pass",
            "--rollback",
            "remove adapter",
        ],
    )
    assert used_result.exit_code == 0, used_result.output
    plan = json.loads(used_result.stdout)
    assert plan["mutation_state"] == "planning-only"

    apply_result = runner.invoke(
        cli,
        [
            "--state-dir",
            str(state),
            "--format",
            "json",
            "apply",
            plan["plan_id"],
            "--fingerprint",
            plan["plan_fingerprint"],
        ],
    )
    assert apply_result.exit_code == 2
    assert json.loads(apply_result.stderr)["error"]["code"] == "unsupported_plan_kind"

    verify_result = runner.invoke(
        cli,
        ["--state-dir", str(state), "--format", "json", "verify", "app_example"],
    )
    assert verify_result.exit_code == 2
    assert json.loads(verify_result.stderr)["error"]["code"] == "invalid_identifier"


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
            "checked",
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
            "checked",
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
    checked_help = runner.invoke(cli, ["checked", "--help"])
    assert version.exit_code == 0
    assert version.stdout == "shoulda, version 0.3.0\n"
    assert help_result.exit_code == 0
    assert "Start here: checked finds options" in help_result.stdout
    assert "Find candidates from an explicit source/query plan" in help_result.stdout
    for command in ("checked", "inspected", "remembered", "rechecked"):
        assert command in help_result.stdout
    for hidden in ("curated", "exported", "projected", "saved", "used", "apply", "verify"):
        assert hidden not in help_result.stdout
    assert checked_help.exit_code == 0
    assert "Explicit discovery source" in checked_help.stdout
    assert "NEED never expands or rewrites it" in " ".join(checked_help.stdout.split())
    assert "Show candidate-level filter and limit reasons" in checked_help.stdout
    assert "default: 5" in checked_help.stdout
