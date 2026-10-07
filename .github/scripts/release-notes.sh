#!/usr/bin/env bash
# Usage: release-notes.sh <version> <output file>
# Writes the CHANGELOG.md section for <version> to <output file>, verbatim:
# the heading line is dropped, and the section ends at the next version heading
# or the link definitions at the bottom. The section was written by a person
# under the release discipline, so nothing here generates prose.
set -euo pipefail

version="$1"
notes="$2"

awk -v heading="## [$version]" '
  index($0, heading) == 1 { inside = 1; next }
  inside && (/^## / || /^\[/) { exit }
  inside { print }
' CHANGELOG.md > "$notes"
if [ ! -s "$notes" ]; then
  echo "::error::The '## [$version]' section of CHANGELOG.md is empty." >&2
  exit 1
fi
