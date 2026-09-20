#!/usr/bin/env python3
"""Verify the built static catalog without making network requests."""

from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE = ROOT / "site"
SITE_PREFIX = "/shoulda-used-that/"
SEARCH_CASES = {
    "problem": "deterministic local python research core",
    "candidate": "pallets/click",
    "covers": "mature command parsing",
    "unresolved": "problem-specific research plan",
    "domain": "python-engineering",
}
RUNTIME_ELEMENTS = {
    "audio": "src",
    "iframe": "src",
    "img": "src",
    "script": "src",
    "source": "src",
    "video": "src",
}


class SiteHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.runtime_resources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids.add(element_id)
        href = attributes.get("href")
        if tag == "a" and href:
            self.links.append(href)
        runtime_attribute = RUNTIME_ELEMENTS.get(tag)
        if runtime_attribute and attributes.get(runtime_attribute):
            self.runtime_resources.append(attributes[runtime_attribute] or "")
        if tag == "link" and href:
            rel = set((attributes.get("rel") or "").split())
            if "canonical" not in rel:
                self.runtime_resources.append(href)
        srcset = attributes.get("srcset")
        if srcset:
            self.runtime_resources.extend(
                candidate.strip().split()[0] for candidate in srcset.split(",") if candidate.strip()
            )


def verify_site(site: Path) -> list[str]:
    problems: list[str] = []
    if not site.is_dir() or site.is_symlink():
        return [f"built site is missing or unsafe: {site}"]
    for path in site.rglob("*"):
        if path.is_symlink():
            problems.append(f"built site contains a symlink: {path.relative_to(site)}")

    pages: dict[Path, SiteHTMLParser] = {}
    for path in sorted(site.rglob("*.html")):
        parser = SiteHTMLParser()
        parser.feed(path.read_text(encoding="utf-8"))
        pages[path] = parser
        for resource in parser.runtime_resources:
            if resource.startswith(("http://", "https://", "//")):
                problems.append(
                    f"{path.relative_to(site)} loads a third-party runtime resource: {resource}"
                )

    if not pages:
        problems.append("built site has no HTML pages")
    for page, parser in pages.items():
        for link in parser.links:
            resolved = _resolve_local_link(site, page, link)
            if resolved is None:
                continue
            target, fragment = resolved
            if not target.is_relative_to(site.resolve()):
                problems.append(f"{page.relative_to(site)} has a link outside the site: {link}")
                continue
            if not target.is_file():
                problems.append(f"{page.relative_to(site)} has a broken local link: {link}")
                continue
            if fragment and target.suffix == ".html":
                target_parser = pages.get(target)
                if target_parser is None:
                    target_parser = SiteHTMLParser()
                    target_parser.feed(target.read_text(encoding="utf-8"))
                if fragment not in target_parser.ids:
                    problems.append(f"{page.relative_to(site)} has a missing fragment: {link}")

    search_path = site / "search.json"
    if not search_path.is_file():
        problems.append("built site has no client search index")
    else:
        try:
            search = json.loads(search_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"client search index is invalid JSON: {exc}")
        else:
            searchable = json.dumps(search, ensure_ascii=False).casefold()
            for label, query in SEARCH_CASES.items():
                if query.casefold() not in searchable:
                    problems.append(f"client search index misses {label} query: {query}")

    manifest_path = site / "curation" / "manifest.json"
    catalog_path = site / "curation" / "catalog.json"
    for label, path in (("manifest", manifest_path), ("catalog", catalog_path)):
        if not path.is_file():
            problems.append(f"built site has no public {label} JSON")
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"public {label} JSON is invalid: {exc}")
    return sorted(set(problems))


def _resolve_local_link(site: Path, page: Path, href: str) -> tuple[Path, str] | None:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or href.startswith("//"):
        return None
    path_value = unquote(parsed.path)
    if path_value.startswith(SITE_PREFIX):
        candidate = site / path_value.removeprefix(SITE_PREFIX)
    elif path_value.startswith("/"):
        return None
    elif path_value:
        candidate = page.parent / path_value
    else:
        candidate = page
    candidate = candidate.resolve(strict=False)
    if path_value.endswith("/") or candidate.is_dir():
        candidate /= "index.html"
    return candidate, unquote(parsed.fragment)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=DEFAULT_SITE)
    args = parser.parse_args()
    problems = verify_site(args.site)
    if problems:
        print("\n".join(problems))
        return 1
    pages = sum(1 for _ in args.site.rglob("*.html"))
    size = sum(path.stat().st_size for path in args.site.rglob("*") if path.is_file())
    print(
        f"verified static site: pages={pages} bytes={size} "
        f"search_cases={len(SEARCH_CASES)} remote_runtime_resources=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
