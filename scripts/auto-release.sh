#!/usr/bin/env bash
# auto-release.sh — create a CalVer GitLab release (vYYYY.MM.N) with wheel asset.
#
# Triggered by .githooks/pre-push after the branch push lands on the remote.
# Can also be run manually:  bash scripts/auto-release.sh <sha> [branch]
#
# Environment: needs the forge token via `mise env`
# (MISE_GITLAB_ENTERPRISE_TOKEN). No glab or jq required — plain curl.
set -euo pipefail
export LC_ALL=C.UTF-8

SHA="${1:?usage: auto-release.sh <sha> [branch] [remote]}"
BRANCH="${2:-main}"
REMOTE="${3:-"$(git config branch.${2:-main}.remote || echo origin)"}"
REMOTE="${REMOTE:-origin}"
API="https://forge.3gpp.org/rep/api/v4"
PROJECT="136"

log() { echo "[auto-release $(date -u +%H:%M:%S)] $*"; }

# --- forge token -----------------------------------------------------------
TOKEN="$(mise env --json 2>/dev/null | sed -n 's/.*"MISE_GITLAB_ENTERPRISE_TOKEN"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
if [ -z "${TOKEN}" ]; then
    log "ERROR: MISE_GITLAB_ENTERPRISE_TOKEN not found via 'mise env'"
    exit 1
fi

# --- wait for the push to land --------------------------------------------
for _ in $(seq 1 60); do
    if git ls-remote "${REMOTE}" "refs/heads/${BRANCH}" 2>/dev/null | grep -q "^${SHA}"; then
        break
    fi
    sleep 2
done
if ! git ls-remote "${REMOTE}" "refs/heads/${BRANCH}" 2>/dev/null | grep -q "^${SHA}"; then
    log "ERROR: ${SHA} not on ${REMOTE}/${BRANCH} after 120s — push rejected? aborting"
    exit 1
fi
log "push ${SHA} landed on ${BRANCH}"

# --- compute next CalVer (YYYY.MM.N, per-month counter) --------------------
PREFIX="$(date -u +%Y.%m)."
LAST_N="$(git ls-remote --tags "${REMOTE}" 2>/dev/null | awk -v p="v${PREFIX}" 'index($2, "refs/tags/" p)==1 { n=$2; sub("refs/tags/" p, "", n); if (n ~ /^[0-9]+$/) print n }' | sort -n | tail -1)"
N="$(( ${LAST_N:-0} + 1 ))"
VERSION="${PREFIX}${N}"
log "next version: v${VERSION}"

# --- release notes: commits since previous CalVer tag ----------------------
git fetch --tags "${REMOTE}" --quiet 2>/dev/null || true
PREV_TAG="$(git ls-remote --tags "${REMOTE}" 2>/dev/null | awk '$2 ~ /refs\/tags\/v20[0-9][0-9]\.[0-9][0-9]\.[0-9][0-9]*$/ { sub("refs/tags/", "", $2); print $2 }' | sort -V | tail -1 || true)"
if [ -n "${PREV_TAG}" ] && [ "${PREV_TAG}" != "v${VERSION}" ]; then
    LOG="$(git log --pretty=format:'* %s (%h)' "${PREV_TAG}..${SHA}" 2>/dev/null || true)"
fi
[ -n "${LOG:-}" ] || LOG="$(git log --pretty=format:'* %s (%h)' "${SHA}" -10 2>/dev/null || true)"

# --- create annotated tag --------------------------------------------------
log "creating tag v${VERSION}"
curl --fail --silent --show-error --request POST \
    --header "PRIVATE-TOKEN: ${TOKEN}" \
    --data-urlencode "tag_name=v${VERSION}" \
    --data-urlencode "ref=${SHA}" \
    --data-urlencode "message=Release v${VERSION}" \
    "${API}/projects/${PROJECT}/repository/tags" >/dev/null

# --- create release --------------------------------------------------------
DESC_FILE="$(mktemp)"
command -v cygpath >/dev/null 2>&1 && DESC_FILE="$(cygpath -w "${DESC_FILE}")"
printf 'Release **v%s**\n\n%s' "${VERSION}" "${LOG}" >"${DESC_FILE}"
log "creating release v${VERSION}"
curl --fail --silent --show-error --request POST \
    --header "PRIVATE-TOKEN: ${TOKEN}" \
    --data-urlencode "name=v${VERSION}" \
    --data-urlencode "tag_name=v${VERSION}" \
    --data-urlencode "description@${DESC_FILE}" \
    "${API}/projects/${PROJECT}/releases" >/dev/null

# --- build wheel & upload as release asset ---------------------------------
log "building wheel"
ROOT="$(git rev-parse --show-toplevel)"
cd "${ROOT}"
uv build --wheel --quiet 2>&1 | tail -1 || log "WARNING: wheel build failed"
WHL="$(ls -t dist/3gpp_crawler-*.whl 2>/dev/null | head -1)"
if [ -n "${WHL}" ]; then
    log "uploading $(basename "${WHL}")"
    curl --fail --silent --show-error --request POST \
        --header "PRIVATE-TOKEN: ${TOKEN}" \
        --form "file=@${WHL}" \
        "${API}/projects/${PROJECT}/uploads" >/dev/null
    # link the uploaded file to the release as a package asset
    UPLOAD_URL="${API}/projects/${PROJECT}/releases/v${VERSION}/assets/links"
    curl --fail --silent --show-error --request POST \
        --header "PRIVATE-TOKEN: ${TOKEN}" \
        --data-urlencode "name=3gpp_crawler-${VERSION}-py3-none-any.whl" \
        --data-urlencode "url=${API}/projects/${PROJECT}/packages/generic/3gpp-crawler/${VERSION}/3gpp_crawler-${VERSION}-py3-none-any.whl" \
        --data-urlencode "link_type=package" \
        "${UPLOAD_URL}" >/dev/null 2>&1 || true
fi
cd - >/dev/null

rm -f "${DESC_FILE}"
log "release v${VERSION} created for ${SHA}"
