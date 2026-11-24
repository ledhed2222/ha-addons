#!/usr/bin/env bash
# Opens or updates a PR bumping the add-on to the latest anki-sync-mcp release.
set -euo pipefail

tag=$(gh release view --repo ledhed2222/anki-sync-mcp --json tagName --jq .tagName)
new_image=${tag#v}
old_image=$(sed -n 's|^FROM ghcr.io/ledhed2222/anki-sync-mcp:||p' anki_mcp/Dockerfile)
echo "current=$old_image latest=$new_image"
[ "$new_image" = "$old_image" ] && exit 0

# The release exists before upstream's image job finishes pushing; try again next run.
docker manifest inspect "ghcr.io/ledhed2222/anki-sync-mcp:$new_image" >/dev/null || exit 0

# One branch, rebuilt from master each time, so later releases replace an unmerged bump instead of conflicting with it.
branch=upstream/anki-sync-mcp
pr=$(gh pr list --head "$branch" --state open --json number --jq '.[0].number // empty')
if [ -n "$pr" ] && git fetch -q origin "$branch" \
    && git show FETCH_HEAD:anki_mcp/Dockerfile | grep -F "anki-sync-mcp:$new_image" >/dev/null; then
  echo "PR #$pr already bumps to $new_image"
  exit 0
fi

old_version=$(sed -n 's/^version: "\(.*\)"$/\1/p' anki_mcp/config.yaml)
IFS=. read -r major minor _ <<<"$old_version"
new_version="$major.$((minor + 1)).0"

sed -i "s|anki-sync-mcp:$old_image|anki-sync-mcp:$new_image|" anki_mcp/Dockerfile anki_mcp/DOCS.md
sed -i "s/^version: \"$old_version\"$/version: \"$new_version\"/" anki_mcp/config.yaml
git diff --stat

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git switch -C "$branch"
git commit -am "Bump anki-sync-mcp to $new_image"
git push --force origin "$branch"
title="Bump anki-sync-mcp to $new_image"
body="Upstream release: https://github.com/ledhed2222/anki-sync-mcp/releases/tag/$tag. Add-on version $old_version -> $new_version."
if [ -n "$pr" ]; then
  gh pr edit "$pr" --title "$title" --body "$body"
else
  gh pr create --base master --head "$branch" --title "$title" --body "$body"
fi
# PRs opened with GITHUB_TOKEN don't fire pull_request workflows, but a dispatch does, and its checks land on the PR's head commit.
gh workflow run ci.yml --ref "$branch"
