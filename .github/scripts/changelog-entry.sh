#!/usr/bin/env bash
# Usage: changelog-entry.sh <addon> <version> <line>. Adds a "## <version>" section to the top unless one exists.
set -euo pipefail

file="$1/CHANGELOG.md"
[ -f "$file" ] || printf '# Changelog\n' >"$file"
grep -qxF "## $2" "$file" && exit 0
{ head -n1 "$file"; printf '\n## %s\n\n- %s\n' "$2" "$3"; tail -n +2 "$file"; } >"$file.tmp"
mv "$file.tmp" "$file"
