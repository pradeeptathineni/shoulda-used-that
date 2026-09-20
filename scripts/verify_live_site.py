#!/usr/bin/env python3
"""Verify the deployed GitHub Pages catalog against committed public bytes."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from scripts.verify_site import SEARCH_CASES, SiteHTMLParser, search_index_problems

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HOST = "pradeeptathineni.github.io"
EXPECTED_PREFIX = "/shoulda-used-that/"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
LIVE_PATHS = (
    "",
    "curation/",
    "curation/catalog.json",
    "curation/manifest.json",
    "search.json",
)


def normalize_base_url(value: str) -> str:
    parsed = urlsplit(value)
    path = parsed.path.rstrip("/") + "/"
    if (
        parsed.scheme != "https"
        or parsed.hostname != EXPECTED_HOST
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or path != EXPECTED_PREFIX
    ):
        raise ValueError(f"live site must be exactly https://{EXPECTED_HOST}{EXPECTED_PREFIX}")
    return f"https://{EXPECTED_HOST}{EXPECTED_PREFIX}"


def fetch_live_payloads(base_url: str, *, timeout: float) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    for relative in LIVE_PATHS:
        url = urljoin(base_url, relative)
        request = Request(  # noqa: S310 - base URL is normalized to one exact HTTPS host
            url,
            headers={"User-Agent": "ShouldaUsedThat-release-verifier/0.2"},
        )
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - exact host is validated
            final = urlsplit(response.geturl())
            if (
                final.scheme != "https"
                or final.hostname != EXPECTED_HOST
                or not final.path.startswith(EXPECTED_PREFIX)
            ):
                raise ValueError(
                    f"live request escaped the expected Pages origin: {response.geturl()}"
                )
            if response.status != 200:
                raise ValueError(f"live path {relative or '/'} returned HTTP {response.status}")
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ValueError(f"live path {relative or '/'} exceeded the response-size cap")
            payloads[relative] = body
    return payloads


def live_payload_problems(
    payloads: dict[str, bytes],
    *,
    expected_catalog: bytes,
    expected_manifest: bytes,
) -> list[str]:
    problems: list[str] = []
    if payloads.get("curation/catalog.json") != expected_catalog:
        problems.append("live catalog JSON differs from the committed artifact")
    if payloads.get("curation/manifest.json") != expected_manifest:
        problems.append("live manifest differs from the committed artifact")

    for relative in ("", "curation/"):
        body = payloads.get(relative, b"")
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"live HTML path {relative or '/'} is not UTF-8")
            continue
        parser = SiteHTMLParser()
        parser.feed(text)
        if "ShouldaUsedThat" not in text:
            problems.append(f"live HTML path {relative or '/'} misses the product identity")
        for resource in parser.runtime_resources:
            resource_url = urlsplit(resource)
            if resource.startswith(("http://", "https://", "//")) and (
                resource_url.scheme != "https" or resource_url.hostname != EXPECTED_HOST
            ):
                problems.append(
                    f"live HTML path {relative or '/'} loads a third-party resource: {resource}"
                )

    try:
        search = json.loads(payloads.get("search.json", b""))
    except (json.JSONDecodeError, UnicodeDecodeError):
        problems.append("live client search index is invalid JSON")
    else:
        problems.extend(
            problem.replace("client search index", "live client search index")
            for problem in search_index_problems(search)
        )
    return sorted(set(problems))


def verify_live_site(
    base_url: str,
    *,
    attempts: int,
    delay_seconds: float,
    timeout: float,
) -> tuple[int, int]:
    if attempts < 1:
        raise ValueError("attempts must be positive")
    normalized = normalize_base_url(base_url)
    expected_catalog = (ROOT / "docs" / "curation" / "catalog.json").read_bytes()
    expected_manifest = (ROOT / "docs" / "curation" / "manifest.json").read_bytes()
    last_error = "live verification did not run"
    for attempt in range(1, attempts + 1):
        try:
            payloads = fetch_live_payloads(normalized, timeout=timeout)
            problems = live_payload_problems(
                payloads,
                expected_catalog=expected_catalog,
                expected_manifest=expected_manifest,
            )
            if problems:
                raise ValueError("; ".join(problems))
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            last_error = str(exc)
            if attempt < attempts:
                time.sleep(delay_seconds)
                continue
            raise RuntimeError(
                f"live Pages verification failed after {attempts} attempts: {last_error}"
            ) from exc
        return len(payloads), sum(len(body) for body in payloads.values())
    raise RuntimeError(last_error)  # pragma: no cover - loop always returns or raises


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--delay-seconds", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    try:
        paths, total_bytes = verify_live_site(
            args.base_url,
            attempts=args.attempts,
            delay_seconds=args.delay_seconds,
            timeout=args.timeout,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(str(exc))
        return 1
    print(
        f"verified live Pages catalog: paths={paths} bytes={total_bytes} "
        f"search_cases={len(SEARCH_CASES)} remote_runtime_resources=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
