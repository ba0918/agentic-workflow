#!/usr/bin/env bash
# Decides whether the current commit releases a new version. Writes
# version=<version> and release=true|false to $GITHUB_OUTPUT, or to stdout
# when run outside Actions. Exits non-zero when the version is half released.
# Needs gh authenticated for this repository and an origin remote.
set -euo pipefail

out="${GITHUB_OUTPUT:-/dev/stdout}"

# plugin.json is the canonical version; CI checks that the other manifests
# follow it.
version="$(jq -r .version .claude-plugin/plugin.json)"
echo "version=$version" >> "$out"

# The tag is read from the remote rather than from a local clone, so the answer
# does not depend on what this checkout happened to fetch.
tagged=no
if [ -n "$(git ls-remote --tags origin "refs/tags/v$version")" ]; then
  tagged=yes
fi
released=no
if gh release view "v$version" --json tagName >/dev/null 2>&1; then
  released=yes
fi
echo "version $version — tagged: $tagged, released: $released" >&2

if [ "$tagged" = yes ] && [ "$released" = yes ]; then
  echo "Already released; this push carries no version change." >&2
  echo "release=false" >> "$out"
  exit 0
fi

# The release job creates the tag and the release in one call, so this state
# only arises from someone doing one of them by hand. A published tag is never
# moved or reused, which makes the way out a person's decision rather than a
# re-run.
if [ "$tagged" != "$released" ]; then
  echo "::error::v$version is half released (tagged: $tagged, released: $released). Resolve it by hand, or release a new version." >&2
  exit 1
fi

# The release commit promotes the Unreleased section to a heading that matches
# the version. Until that commit lands, a push carrying the manifests' version
# without its heading is an ordinary push — the manifests name the next version
# before its notes are written — and is not a release. The heading is the part
# a machine can check, and checking it here is what keeps the notes from being
# written after the fact.
if ! grep -qF "## [$version]" CHANGELOG.md; then
  echo "No '## [$version]' heading in CHANGELOG.md; this push is not a release." >&2
  echo "release=false" >> "$out"
  exit 0
fi
echo "release=true" >> "$out"
