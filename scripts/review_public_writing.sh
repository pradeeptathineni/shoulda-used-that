#!/usr/bin/env bash
set -euo pipefail

vale_bin="${VALE_BIN:-vale}"
if ! command -v "$vale_bin" >/dev/null 2>&1; then
  echo "Vale 3.21.0 is required; install it or set VALE_BIN to its executable." >&2
  exit 1
fi

vale_version="$("$vale_bin" --version)"
if [[ "$vale_version" != "vale version 3.21.0" ]]; then
  echo "Vale 3.21.0 is required; found: $vale_version" >&2
  exit 1
fi

"$vale_bin" --config=.vale.ini --minAlertLevel=warning \
  README.md \
  docs/index.md \
  docs/curation/index.md \
  docs/curation/dogfood.md \
  docs/curation/in-use.md \
  docs/architecture/public-writing.md
