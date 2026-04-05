#!/usr/bin/env bash
set -euo pipefail

# ContextLedger Skill Diff — GitHub Action entrypoint
# Detects changed skill profiles in a PR, runs semantic diff,
# posts results as a PR comment, and blocks merge on tier 3 conflicts.

CHANGED_PROFILES="${INPUT_CHANGED_PROFILES:-auto}"
POST_COMMENT="${INPUT_POST_COMMENT:-true}"
TIER3_FOUND=0
COMMENT_BODY=""

# ---------- discover changed profiles ----------

if [ "$CHANGED_PROFILES" = "auto" ]; then
  if [ -z "${GITHUB_BASE_REF:-}" ] || [ -z "${GITHUB_HEAD_REF:-}" ]; then
    echo "::error::GITHUB_BASE_REF or GITHUB_HEAD_REF not set. This action must run on pull_request events."
    exit 1
  fi

  # Ensure we have the base branch available for diffing
  git fetch origin "$GITHUB_BASE_REF" --depth=1 2>/dev/null || true

  PROFILES=$(git diff --name-only "origin/${GITHUB_BASE_REF}...HEAD" | grep 'profile\.yaml$' || true)
else
  # Convert comma-separated list to newline-separated
  PROFILES=$(echo "$CHANGED_PROFILES" | tr ',' '\n' | sed 's/^ *//;s/ *$//')
fi

if [ -z "$PROFILES" ]; then
  echo "No changed skill profiles detected. Nothing to diff."
  exit 0
fi

echo "Changed profiles:"
echo "$PROFILES"
echo ""

# ---------- build diff report ----------

COMMENT_BODY="## ContextLedger Skill Diff Report"$'\n\n'

PROFILE_COUNT=0
CONFLICT_SUMMARY=""

while IFS= read -r profile_path; do
  [ -z "$profile_path" ] && continue
  PROFILE_COUNT=$((PROFILE_COUNT + 1))

  # Extract skill name from path (e.g. skills/my-skill/profile.yaml -> my-skill)
  skill_name=$(echo "$profile_path" | sed -E 's|.*/([^/]+)/profile\.yaml$|\1|')
  if [ "$skill_name" = "$profile_path" ]; then
    # Fallback: use the full path as the name
    skill_name="$profile_path"
  fi

  echo "--- Diffing skill: $skill_name ($profile_path) ---"
  COMMENT_BODY+="### Skill: \`${skill_name}\`"$'\n'
  COMMENT_BODY+="**Path:** \`${profile_path}\`"$'\n\n'

  # Run the contextledger diff command and capture output
  DIFF_OUTPUT=""
  DIFF_EXIT=0
  DIFF_OUTPUT=$(python -m contextledger diff --base "origin/${GITHUB_BASE_REF:-main}" --head HEAD -- "$profile_path" 2>&1) || DIFF_EXIT=$?

  if [ $DIFF_EXIT -eq 0 ] && [ -z "$DIFF_OUTPUT" ]; then
    COMMENT_BODY+="No semantic differences detected."$'\n\n'
    continue
  fi

  # Parse diff output for conflict tiers
  HAS_TIER3=0
  HAS_TIER2=0
  HAS_TIER1=0

  if echo "$DIFF_OUTPUT" | grep -qi "tier.3\|tier_3\|MANUAL_OVERRIDE\|BLOCKED"; then
    HAS_TIER3=1
    TIER3_FOUND=1
  fi
  if echo "$DIFF_OUTPUT" | grep -qi "tier.2\|tier_2\|SEMANTIC_EVAL"; then
    HAS_TIER2=1
  fi
  if echo "$DIFF_OUTPUT" | grep -qi "tier.1\|tier_1\|AUTO_MERGE"; then
    HAS_TIER1=1
  fi

  # Section: conflict tier summary for this skill
  if [ $HAS_TIER3 -eq 1 ]; then
    COMMENT_BODY+="> :no_entry: **Tier 3 conflict detected — merge blocked until resolved manually.**"$'\n\n'
    CONFLICT_SUMMARY+="- \`${skill_name}\`: :no_entry: Tier 3 (manual override required)"$'\n'
  elif [ $HAS_TIER2 -eq 1 ]; then
    COMMENT_BODY+="> :warning: **Tier 2 conflict — semantic evaluation recommended.**"$'\n\n'
    CONFLICT_SUMMARY+="- \`${skill_name}\`: :warning: Tier 2 (semantic evaluation)"$'\n'
  elif [ $HAS_TIER1 -eq 1 ]; then
    COMMENT_BODY+="> :white_check_mark: **Tier 1 — auto-mergeable.**"$'\n\n'
    CONFLICT_SUMMARY+="- \`${skill_name}\`: :white_check_mark: Tier 1 (auto-merge)"$'\n'
  fi

  # Include the raw diff output in a collapsible section
  COMMENT_BODY+="<details>"$'\n'
  COMMENT_BODY+="<summary>Full diff output</summary>"$'\n\n'
  COMMENT_BODY+='```'$'\n'
  COMMENT_BODY+="$DIFF_OUTPUT"$'\n'
  COMMENT_BODY+='```'$'\n\n'
  COMMENT_BODY+="</details>"$'\n\n'

  # Also run a raw YAML diff as a fallback / supplementary view
  if git show "origin/${GITHUB_BASE_REF:-main}:${profile_path}" > /dev/null 2>&1; then
    RAW_DIFF=$(git diff "origin/${GITHUB_BASE_REF:-main}...HEAD" -- "$profile_path" 2>/dev/null || true)
    if [ -n "$RAW_DIFF" ]; then
      COMMENT_BODY+="<details>"$'\n'
      COMMENT_BODY+="<summary>Raw YAML diff</summary>"$'\n\n'
      COMMENT_BODY+='```diff'$'\n'
      COMMENT_BODY+="$RAW_DIFF"$'\n'
      COMMENT_BODY+='```'$'\n\n'
      COMMENT_BODY+="</details>"$'\n\n'
    fi
  else
    COMMENT_BODY+="*New profile (no base version to compare against).*"$'\n\n'
  fi

done <<< "$PROFILES"

# ---------- summary ----------

COMMENT_BODY+="---"$'\n'
COMMENT_BODY+="### Summary"$'\n\n'
COMMENT_BODY+="**Profiles analyzed:** ${PROFILE_COUNT}"$'\n\n'

if [ -n "$CONFLICT_SUMMARY" ]; then
  COMMENT_BODY+="$CONFLICT_SUMMARY"$'\n'
fi

if [ $TIER3_FOUND -eq 1 ]; then
  COMMENT_BODY+=$'\n'":no_entry: **Merge blocked — tier 3 conflicts require manual resolution.**"$'\n'
else
  COMMENT_BODY+=$'\n'":white_check_mark: **No blocking conflicts found.**"$'\n'
fi

echo ""
echo "========== DIFF REPORT =========="
echo "$COMMENT_BODY"
echo "================================="

# ---------- post PR comment ----------

if [ "$POST_COMMENT" = "true" ]; then
  PR_NUMBER="${GITHUB_PR_NUMBER:-}"

  # Try to extract PR number from GITHUB_REF if not set
  if [ -z "$PR_NUMBER" ]; then
    PR_NUMBER=$(echo "${GITHUB_REF:-}" | grep -oP 'pull/\K[0-9]+' || true)
  fi

  # Try gh pr view as last resort
  if [ -z "$PR_NUMBER" ]; then
    PR_NUMBER=$(gh pr view --json number -q '.number' 2>/dev/null || true)
  fi

  if [ -n "$PR_NUMBER" ]; then
    echo "$COMMENT_BODY" | gh pr comment "$PR_NUMBER" --body-file -
    echo "Posted diff report as PR comment on #${PR_NUMBER}."
  else
    echo "::warning::Could not determine PR number. Skipping comment post."
  fi
fi

# ---------- exit code ----------

if [ $TIER3_FOUND -eq 1 ]; then
  echo "::error::Tier 3 conflicts detected. Merge is blocked."
  exit 1
fi

echo "Skill diff completed successfully."
exit 0
