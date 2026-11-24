#!/usr/bin/env bash
# Tags each add-on as <dir>-v<version> and releases it with that version's changelog section; a version that already has a release is skipped.
set -euo pipefail

for config in */config.yaml; do
  addon=${config%/config.yaml}
  version=$(sed -n 's/^version: "\(.*\)"$/\1/p' "$config")
  tag="$addon-v$version"
  if gh release view "$tag" >/dev/null 2>&1; then
    echo "$tag already released"
    continue
  fi
  notes=$(awk -v h="## $version" '$0 == h {f = 1; next} /^## / {f = 0} f' "$addon/CHANGELOG.md" 2>/dev/null || true)
  if [ -n "${notes//[[:space:]]/}" ]; then
    gh release create "$tag" --target "$GITHUB_SHA" --title "$addon $version" --notes "$notes"
  else
    gh release create "$tag" --target "$GITHUB_SHA" --title "$addon $version" --generate-notes
  fi
done
