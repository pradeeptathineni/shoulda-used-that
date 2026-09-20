from __future__ import annotations

import json

import pytest

from scripts.verify_live_site import live_payload_problems, normalize_base_url
from scripts.verify_site import SEARCH_CASES


def _payloads(*, runtime_resource: str | None = None) -> dict[str, bytes]:
    resource = f'<script src="{runtime_resource}"></script>' if runtime_resource else ""
    html = f"<!doctype html><title>ShouldaUsedThat</title>{resource}".encode()
    search = {
        "items": [
            {
                "location": "curation/briefs/example/",
                "text": " ".join(SEARCH_CASES.values()),
            }
        ]
    }
    return {
        "": html,
        "curation/": html,
        "curation/catalog.json": b"{}\n",
        "curation/manifest.json": b"{}\n",
        "search.json": json.dumps(search).encode(),
    }


def test_live_site_url_is_exactly_bounded() -> None:
    expected = "https://pradeeptathineni.github.io/shoulda-used-that/"
    assert normalize_base_url(expected) == expected
    assert normalize_base_url(expected.rstrip("/")) == expected
    for unsafe in (
        "http://pradeeptathineni.github.io/shoulda-used-that/",
        "https://example.com/shoulda-used-that/",
        "https://pradeeptathineni.github.io/another-project/",
        "https://pradeeptathineni.github.io/shoulda-used-that/?redirect=example.com",
    ):
        with pytest.raises(ValueError, match="must be exactly"):
            normalize_base_url(unsafe)


def test_live_payloads_match_committed_bytes_search_and_runtime_boundary() -> None:
    payloads = _payloads()
    assert (
        live_payload_problems(
            payloads,
            expected_catalog=b"{}\n",
            expected_manifest=b"{}\n",
        )
        == []
    )

    hostile = _payloads(runtime_resource="https://tracker.example/script.js")
    hostile["curation/catalog.json"] = b'{"changed":true}\n'
    problems = live_payload_problems(
        hostile,
        expected_catalog=b"{}\n",
        expected_manifest=b"{}\n",
    )
    assert "live catalog JSON differs from the committed artifact" in problems
    assert any("third-party resource" in item for item in problems)

    hostile_search = _payloads()
    search = json.loads(hostile_search["search.json"])
    search["items"].append({"location": "curation/evidence/example/", "text": "deep evidence"})
    hostile_search["search.json"] = json.dumps(search).encode()
    problems = live_payload_problems(
        hostile_search,
        expected_catalog=b"{}\n",
        expected_manifest=b"{}\n",
    )
    assert "live client search index includes deep evidence pages" in problems
