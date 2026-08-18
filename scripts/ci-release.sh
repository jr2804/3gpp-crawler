#!/usr/bin/env bash
# ci-release.sh — called from GitLab CI to create CalVer release with wheel.
set -euo pipefail

PREFIX="$(date -u +%Y.%m)."
LAST_N="$(curl --silent --header "PRIVATE-TOKEN: ${CI_RELEASE_TOKEN}" \
  "https://forge.3gpp.org/rep/api/v4/projects/${CI_PROJECT_ID}/repository/tags" \
  | python3 -c "
import json, sys, re
tags = json.load(sys.stdin)
prefix = 'v${PREFIX}'
ns = [int(t['name'][len(prefix):]) for t in tags if t['name'].startswith(prefix) and re.match(r'^\d+$', t['name'][len(prefix):])]
print(max(ns) if ns else 0)
")"
N="$(( LAST_N + 1 ))"
VERSION="${PREFIX}${N}"

echo "CalVer: v${VERSION}"

# --- tag the commit (via API) ---
curl --fail --silent --show-error --request POST \
  --header "PRIVATE-TOKEN: ${CI_RELEASE_TOKEN}" \
  --data-urlencode "tag_name=v${VERSION}" \
  --data-urlencode "ref=${CI_COMMIT_SHA}" \
  --data-urlencode "message=Release v${VERSION}" \
  "https://forge.3gpp.org/rep/api/v4/projects/${CI_PROJECT_ID}/repository/tags"

# --- build wheel with correct version ---
sed -i 's/^__version__ = ".*"/__version__ = "'"${VERSION}"'"/' src/tdoc_crawler/__init__.py
sed -i 's/^version = ".*"/version = "'"${VERSION}"'"/' pyproject.toml
uv build --wheel --quiet

# --- create release ---
LOG="$(git log --pretty=format:'* %s (%h)' -10 "${CI_COMMIT_SHA}")"
DESCRIPTION="Release **v${VERSION}**

${LOG}"
curl --fail --silent --show-error --request POST \
  --header "PRIVATE-TOKEN: ${CI_RELEASE_TOKEN}" \
  --data-urlencode "name=v${VERSION}" \
  --data-urlencode "tag_name=v${VERSION}" \
  --data-urlencode "description=${DESCRIPTION}" \
  "https://forge.3gpp.org/rep/api/v4/projects/${CI_PROJECT_ID}/releases"

# --- upload wheel as asset ---
WHL="$(ls dist/3gpp_crawler-*.whl 2>/dev/null | head -1)"
if [ -n "${WHL}" ]; then
  curl --fail --silent --show-error --request POST \
    --header "PRIVATE-TOKEN: ${CI_RELEASE_TOKEN}" \
    --form "file=@${WHL}" \
    "https://forge.3gpp.org/rep/api/v4/projects/${CI_PROJECT_ID}/uploads" >/dev/null

  curl --fail --silent --show-error --request POST \
    --header "PRIVATE-TOKEN: ${CI_RELEASE_TOKEN}" \
    --data-urlencode "name=3gpp_crawler-${VERSION}-py3-none-any.whl" \
    --data-urlencode "link_type=package" \
    --data-urlencode "url=https://forge.3gpp.org/rep/api/v4/projects/${CI_PROJECT_ID}/packages/generic/3gpp-crawler/${VERSION}/3gpp_crawler-${VERSION}-py3-none-any.whl" \
    "https://forge.3gpp.org/rep/api/v4/projects/${CI_PROJECT_ID}/releases/v${VERSION}/assets/links"
fi

echo "Release v${VERSION} created"
