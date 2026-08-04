#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="ericel/weynear-templates"
WORKFLOW="build-template.yml"
PUBLISHER="weynear"
APPROVE_PRODUCTION=0
WATCH_RUN=1

usage() {
  cat <<'EOF'
Usage:
  scripts/trigger_template_deployment.sh <template-name> <version> [options]

Options:
  --publisher <publisher>  Registry publisher (default: weynear)
  --approve                Approve automation-registry-production when requested
  --no-watch               Return after dispatching the workflow

Examples:
  scripts/trigger_template_deployment.sh news-feed-publisher 1.0.0 --approve
  scripts/trigger_template_deployment.sh sports-live-scores 2.2.0 --no-watch

The command always dispatches the workflow from GitHub's remote main branch.
It does not pull, merge, push, or depend on the state of the local checkout.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 2 ]]; then
  usage >&2
  exit 2
fi

TEMPLATE_NAME="$1"
TEMPLATE_VERSION="$2"
shift 2

while [[ $# -gt 0 ]]; do
  case "$1" in
    --publisher)
      [[ $# -ge 2 ]] || { echo "--publisher requires a value" >&2; exit 2; }
      PUBLISHER="$2"
      shift 2
      ;;
    --approve)
      APPROVE_PRODUCTION=1
      shift
      ;;
    --no-watch)
      WATCH_RUN=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

IDENTIFIER_PATTERN='^[a-z][a-z0-9-]{1,62}$'
SEMVER_PATTERN='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'
[[ "$PUBLISHER" =~ $IDENTIFIER_PATTERN ]] || {
  echo "Invalid publisher identifier: $PUBLISHER" >&2
  exit 2
}
[[ "$TEMPLATE_NAME" =~ $IDENTIFIER_PATTERN ]] || {
  echo "Invalid template identifier: $TEMPLATE_NAME" >&2
  exit 2
}
[[ "$TEMPLATE_VERSION" =~ $SEMVER_PATTERN ]] || {
  echo "Version must use strict semantic versioning: $TEMPLATE_VERSION" >&2
  exit 2
}

for command_name in gh jq; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "Required command is not installed: $command_name" >&2
    exit 1
  }
done
gh auth status >/dev/null

RECIPE_PATH="registry/recipes/${PUBLISHER}/${TEMPLATE_NAME}/${TEMPLATE_VERSION}/template.yaml"
if ! gh api \
  -H "Accept: application/vnd.github.raw+json" \
  "repos/${REPOSITORY}/contents/${RECIPE_PATH}?ref=main" \
  >/dev/null 2>&1; then
  echo "Remote main does not contain ${PUBLISHER}/${TEMPLATE_NAME}@${TEMPLATE_VERSION}." >&2
  echo "Merge its source-only contribution before triggering a deployment." >&2
  exit 1
fi

active_run="$({
  gh api --method GET \
    "repos/${REPOSITORY}/actions/workflows/${WORKFLOW}/runs" \
    -f branch=main \
    -f event=workflow_dispatch \
    -f per_page=20
} | jq -r '.workflow_runs[] | select(.status != "completed") | [.id, .status, .html_url] | @tsv' | head -n 1)"
if [[ -n "$active_run" ]]; then
  IFS=$'\t' read -r active_id active_status active_url <<<"$active_run"
  echo "A central template deployment is already ${active_status}: ${active_url}" >&2
  echo "Run ID: ${active_id}" >&2
  exit 1
fi

dispatch_started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Dispatching ${PUBLISHER}/${TEMPLATE_NAME}@${TEMPLATE_VERSION} from remote main..."
gh workflow run "$WORKFLOW" \
  --repo "$REPOSITORY" \
  --ref main \
  -f "publisher=${PUBLISHER}" \
  -f "name=${TEMPLATE_NAME}" \
  -f "version=${TEMPLATE_VERSION}"

run_id=""
run_url=""
for _attempt in {1..30}; do
  run_row="$({
    gh api --method GET \
      "repos/${REPOSITORY}/actions/workflows/${WORKFLOW}/runs" \
      -f branch=main \
      -f event=workflow_dispatch \
      -f per_page=20
  } | jq -r --arg started "$dispatch_started_at" \
    '.workflow_runs[] | select(.created_at >= $started) | [.id, .html_url] | @tsv' \
    | head -n 1)"
  if [[ -n "$run_row" ]]; then
    IFS=$'\t' read -r run_id run_url <<<"$run_row"
    break
  fi
  sleep 2
done

if [[ -z "$run_id" ]]; then
  echo "The workflow was dispatched, but its run ID was not visible within 60 seconds." >&2
  echo "Inspect: https://github.com/${REPOSITORY}/actions/workflows/${WORKFLOW}" >&2
  exit 1
fi
echo "Triggered run ${run_id}: ${run_url}"

if [[ "$APPROVE_PRODUCTION" -eq 1 ]]; then
  echo "Waiting for the protected production approval request..."
  approved=0
  for _attempt in {1..120}; do
    run_status="$(gh run view "$run_id" --repo "$REPOSITORY" --json status --jq '.status')"
    if [[ "$run_status" == "completed" ]]; then
      break
    fi
    pending="$({
      gh api "repos/${REPOSITORY}/actions/runs/${run_id}/pending_deployments"
    } 2>/dev/null || printf '[]')"
    environment_id="$(jq -r \
      '.[] | select(.environment.name == "automation-registry-production" and .current_user_can_approve == true) | .environment.id' \
      <<<"$pending" | head -n 1)"
    if [[ -n "$environment_id" ]]; then
      gh api --method POST \
        "repos/${REPOSITORY}/actions/runs/${run_id}/pending_deployments" \
        -F "environment_ids[]=${environment_id}" \
        -f state=approved \
        -f comment="Approved by trigger_template_deployment.sh for ${PUBLISHER}/${TEMPLATE_NAME}@${TEMPLATE_VERSION}." \
        >/dev/null
      echo "Approved automation-registry-production."
      approved=1
      break
    fi
    sleep 2
  done
  if [[ "$approved" -ne 1 ]]; then
    echo "No approvable production deployment appeared for run ${run_id}." >&2
  fi
fi

if [[ "$WATCH_RUN" -eq 1 ]]; then
  gh run watch "$run_id" --repo "$REPOSITORY" --exit-status
fi
