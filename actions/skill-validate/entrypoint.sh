#!/usr/bin/env bash
set -euo pipefail

# ContextLedger Skill Validate — GitHub Action entrypoint
# Reads a project manifest, extracts declared skills,
# and verifies each skill's profile.yaml exists on disk.

MANIFEST="${INPUT_PROJECT_MANIFEST:-.contextledger/project.yaml}"

# ---------- check manifest exists ----------

if [ ! -f "$MANIFEST" ]; then
  echo "::error::Project manifest not found at '${MANIFEST}'."
  exit 1
fi

echo "Validating skills declared in: ${MANIFEST}"
echo ""

# ---------- extract skills list from YAML ----------

# Use Python + PyYAML for reliable YAML parsing.
SKILLS=$(python3 -c "
import sys, yaml

try:
    with open('${MANIFEST}', 'r') as f:
        data = yaml.safe_load(f)
except Exception as e:
    print(f'ERROR: Failed to parse manifest: {e}', file=sys.stderr)
    sys.exit(1)

if data is None:
    print('ERROR: Manifest is empty.', file=sys.stderr)
    sys.exit(1)

skills = data.get('skills', [])
if not skills:
    print('WARNING: No skills declared in manifest.', file=sys.stderr)
    sys.exit(0)

# Skills can be strings (skill names) or dicts with a 'name' key
for skill in skills:
    if isinstance(skill, str):
        print(skill)
    elif isinstance(skill, dict) and 'name' in skill:
        print(skill['name'])
    else:
        print(f'WARNING: Unrecognized skill entry: {skill}', file=sys.stderr)
")

if [ -z "$SKILLS" ]; then
  echo "No skills declared in manifest. Nothing to validate."
  exit 0
fi

# ---------- determine skills directory ----------

# The skills directory is relative to the manifest location.
MANIFEST_DIR=$(dirname "$MANIFEST")
SKILLS_DIR="${MANIFEST_DIR}/skills"

# Also check project root level skills/ as a fallback
if [ ! -d "$SKILLS_DIR" ]; then
  SKILLS_DIR="skills"
fi

echo "Skills directory: ${SKILLS_DIR}"
echo ""

# ---------- validate each skill ----------

PASS_COUNT=0
FAIL_COUNT=0
TOTAL_COUNT=0
REPORT=""

while IFS= read -r skill_name; do
  [ -z "$skill_name" ] && continue
  TOTAL_COUNT=$((TOTAL_COUNT + 1))

  PROFILE_PATH="${SKILLS_DIR}/${skill_name}/profile.yaml"

  if [ -f "$PROFILE_PATH" ]; then
    PASS_COUNT=$((PASS_COUNT + 1))
    STATUS="PASS"
    ICON="[OK]"
    echo "${ICON} ${skill_name} -> ${PROFILE_PATH}"
    REPORT+="- :white_check_mark: \`${skill_name}\` — \`${PROFILE_PATH}\` exists"$'\n'
  else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    STATUS="FAIL"
    ICON="[MISSING]"
    echo "::error::${ICON} ${skill_name} -> ${PROFILE_PATH} NOT FOUND"
    REPORT+="- :x: \`${skill_name}\` — \`${PROFILE_PATH}\` **not found**"$'\n'
  fi

done <<< "$SKILLS"

# ---------- summary ----------

echo ""
echo "========================================="
echo "Validation Summary"
echo "========================================="
echo "Total skills:   ${TOTAL_COUNT}"
echo "Passed:         ${PASS_COUNT}"
echo "Failed:         ${FAIL_COUNT}"
echo "========================================="

# Write summary to GitHub Actions step summary if available
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "## ContextLedger Skill Validation"
    echo ""
    echo "**Manifest:** \`${MANIFEST}\`"
    echo ""
    echo "$REPORT"
    echo ""
    echo "**Total:** ${TOTAL_COUNT} | **Passed:** ${PASS_COUNT} | **Failed:** ${FAIL_COUNT}"
  } >> "$GITHUB_STEP_SUMMARY"
fi

# ---------- exit code ----------

if [ $FAIL_COUNT -gt 0 ]; then
  echo ""
  echo "::error::${FAIL_COUNT} skill(s) declared in manifest but missing profile.yaml."
  exit 1
fi

echo ""
echo "All declared skills validated successfully."
exit 0
