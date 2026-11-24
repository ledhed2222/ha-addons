#!/usr/bin/env bash
# Fails a PR that changes anki_mcp (other than its changelog) without raising its version. Expects GITHUB_BASE_REF.
set -euo pipefail

git fetch -q --depth=1 origin "$GITHUB_BASE_REF"
git diff --quiet FETCH_HEAD -- anki_mcp ':!anki_mcp/CHANGELOG.md' && exit 0
old=$(git show FETCH_HEAD:anki_mcp/config.yaml | sed -n 's/^version: "\(.*\)"$/\1/p')
new=$(sed -n 's/^version: "\(.*\)"$/\1/p' anki_mcp/config.yaml)
echo "base version=$old, PR version=$new"
uv run --no-project --with awesomeversion python -I -c 'import sys; from awesomeversion import AwesomeVersion as V; sys.exit(0 if V(sys.argv[2]) > V(sys.argv[1]) else 1)' "$old" "$new"
