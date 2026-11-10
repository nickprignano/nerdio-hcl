#!/usr/bin/env bash
# File the drift workflow's results (.github/workflows/drift.yml) as GitHub issues: one open issue
# per environment, labelled infra-drift, updated while the drift lasts and closed once a run is
# clean. Reads the drift-<env>-<stage> artifacts stage.yml leaves; needs only issues: write.
#
#   scripts/pipeline/drift-report.sh <dir of downloaded artifacts>
#
# The summaries were masked by stage.sh; they are masked again here before posting, because the
# issue is public on a public repository.
set -euo pipefail

dir="${1:?usage: $0 <artifacts dir>}"
: "${REPO:?}" "${RUN_URL:?}"
label=infra-drift
redact() { sed -E 's/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/<id>/g'; }

shopt -s nullglob
results=("$dir"/*/result.json)
if [ "${#results[@]}" = 0 ]; then
  echo "::warning::No drift results to report; every leg failed before it could leave one. See $RUN_URL"
  exit 0
fi

gh label create "$label" --repo "$REPO" --color b60205 \
  --description "Azure or Nerdio differ from main (drift.yml)" >/dev/null 2>&1 || true

mapfile -t envs < <(jq -r .environment "${results[@]}" | sort -u)
for env in "${envs[@]}"; do
  [[ "$env" =~ ^[a-z][a-z0-9-]{1,20}$ ]] || continue
  title="Drift: $env"
  body="$(mktemp)"
  worst=clean
  {
    echo "The daily read-only plan found differences between \`main\` and what's deployed in **$env**."
    echo "That is either a change made outside the pipeline (the portal, Nerdio's console, a script)"
    echo "or code merged to \`main\` that was never applied. Nothing was changed."
    echo
    echo "To restore what \`main\` declares, run **deploy** for this environment with apply ticked; a"
    echo "reviewer approves the apply. To keep an outside change, change the code or answers to match."
    echo
    echo "| Stage | Result |"
    echo "|---|---|"
  } > "$body"
  for f in "${results[@]}"; do
    [ "$(jq -r .environment "$f")" = "$env" ] || continue
    stage="$(jq -r .stage "$f")"
    status="$(jq -r .status "$f")"
    echo "| $stage | $status |" >> "$body"
    case "$status" in
      clean) ;;
      drift) [ "$worst" = failure ] || worst=drift ;;
      *) worst=failure ;;
    esac
  done
  for f in "${results[@]}"; do
    [ "$(jq -r .environment "$f")" = "$env" ] || continue
    [ "$(jq -r .status "$f")" != clean ] || continue
    md="$(dirname "$f")/summary.md"
    [ -s "$md" ] || continue
    { echo; echo "<details><summary>$(jq -r .stage "$f")</summary>"; echo; head -c 20000 "$md" | redact; echo; echo "</details>"; } >> "$body"
  done
  echo >> "$body"
  echo "[Drift run]($RUN_URL)" >> "$body"

  number="$(gh issue list --repo "$REPO" --label "$label" --state open --limit 100 --json number,title \
    --jq ".[] | select(.title == \"$title\") | .number" | head -n1)"
  if [ "$worst" = clean ]; then
    if [ -n "$number" ]; then
      gh issue close "$number" --repo "$REPO" --comment "No drift in today's run: $RUN_URL" >/dev/null
      echo "$env: clean, closed #$number"
    else
      echo "$env: clean"
    fi
  elif [ -n "$number" ]; then
    gh issue edit "$number" --repo "$REPO" --body-file "$body" >/dev/null
    gh issue comment "$number" --repo "$REPO" --body "Still $worst in today's run: $RUN_URL" >/dev/null
    echo "$env: $worst, updated #$number"
  else
    gh issue create --repo "$REPO" --title "$title" --label "$label" --body-file "$body" >/dev/null
    echo "$env: $worst, opened an issue"
  fi
  rm -f "$body"
done
