#!/usr/bin/env bash
# auto-release.sh — create a CalVer GitLab release (vYYYY.MM.N) after a push.
#
# Triggered by .githooks/pre-push after the branch push lands on the remote.
# Can also be run manually:  bash scripts/auto-release.sh <sha> [branch]
#
# Environment: needs the forge token via `mise env`
# (MISE_GITLAB_ENTERPRISE_TOKEN). No glab or jq required — plain curl.
set -euo pipefail
export LC_ALL=C.UTF-8 # keep emoji in commit subjects readable in release notes

SHA="${1:?usage: auto-release.sh <sha> [branch] [remote]}"
BRANCH="${2:-main}"
REMOTE="${3:-"$(git config branch.${2:-main}.remote || echo origin)"}"
REMOTE="${REMOTE:-origin}"
API="https://forge.3gpp.org/rep/api/v4"
PROJECT="136" # reimes/3gpp-crawler

log() { echo "[auto-release $(date -u +%H:%M:%S)] $*"; }

# --- forge token -----------------------------------------------------------
# sed instead of python: bare `python` is not on PATH in hook environments
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
DESCRIPTION="Release **v${VERSION}**\n\n${LOG}"

# --- create annotated tag --------------------------------------------------
log "creating tag v${VERSION}"
curl --fail --silent --show-error --request POST \
    --header "PRIVATE-TOKEN: ${TOKEN}" \
    --data-urlencode "tag_name=v${VERSION}" \
    --data-urlencode "ref=${SHA}" \
    --data-urlencode "message=Release v${VERSION}" \
    "${API}/projects/${PROJECT}/repository/tags" >/dev/null

# --- create release --------------------------------------------------------
log "creating release v${VERSION}"
curl --fail --silent --show-error --request POST \
    --header "PRIVATE-TOKEN: ${TOKEN}" \
    --data-urlencode "name=v${VERSION}" \
    --data-urlencode "tag_name=v${VERSION}" \
    --data-urlencode "description=${DESCRIPTION}" \
    "${API}/projects/${PROJECT}/releases" >/dev/null

log "release v${VERSION} created for ${SHA}"
