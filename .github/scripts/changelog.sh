#!/usr/bin/env bash
# Adds a changelog entry for each add-on whose version this PR bumps, pushes it to the PR branch, and reruns CI there.
# Expects TITLE, NUMBER and BRANCH (the PR's) and GITHUB_BASE_REF.
set -euo pipefail

git fetch -q --depth=1 origin "$GITHUB_BASE_REF"
for config in */config.yaml; do
  addon=${config%/config.yaml}
  old=$(git show "FETCH_HEAD:$config" 2>/dev/null | sed -n 's/^version: "\(.*\)"$/\1/p' || true)
  new=$(sed -n 's/^version: "\(.*\)"$/\1/p' "$config")
  [ "$old" = "$new" ] && continue
  .github/scripts/changelog-entry.sh "$addon" "$new" "$TITLE (#$NUMBER)"
done
git add -- */CHANGELOG.md
git diff --cached --quiet && exit 0
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git commit -m "Add changelog entry for #$NUMBER"
git push origin "HEAD:$BRANCH"
# Pushes made with GITHUB_TOKEN don't fire pull_request workflows, but a dispatch does, and its checks land on the new head.
gh workflow run ci.yml --ref "$BRANCH"
