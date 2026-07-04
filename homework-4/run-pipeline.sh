#!/usr/bin/env bash
#
# Homework 4 — one-command, four-agent bug-fixing pipeline.
#
# Runs four agents headlessly via `claude -p`, in order, each with the model
# declared in its own agents/*.agent.md frontmatter, auto-loading the skill that
# agent references. Read-only agents are hard-restricted from editing code.
#
#   Stage 1  Research Verifier  -> verified-research.md   (read-only)
#   Stage 2  Bug Fixer          -> fix-summary.md         (edits + runs tests)
#   Stage 3  Security Verifier  -> security-report.md     (read-only)
#   Stage 4  Unit Test Generator-> test-report.md         (edits + runs tests)
#
# Usage:  ./run-pipeline.sh        (or: npm run pipeline)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

CTX="context/bugs/001"

if ! command -v claude >/dev/null 2>&1; then
  echo "ERROR: the 'claude' CLI is not on PATH. Install Claude Code first." >&2
  exit 1
fi

# --- frontmatter helpers -----------------------------------------------------

# frontmatter_value <key> <file>  -> prints the value of a key inside the
# leading YAML frontmatter block (the part between the first two '---' lines).
frontmatter_value() {
  awk -v key="$1" '
    /^---[[:space:]]*$/ { d++; next }
    d==1 && $0 ~ "^"key":" { sub("^"key":[[:space:]]*", ""); print; exit }
  ' "$2"
}

# agent_body <file> -> prints everything after the frontmatter (the system prompt).
agent_body() {
  awk '/^---[[:space:]]*$/ { d++; next } d>=2 { print }' "$1"
}

# build_system_prompt <agent-file> -> agent body + inlined skill (if any).
build_system_prompt() {
  local file="$1"
  local body skill
  body="$(agent_body "$file")"
  skill="$(frontmatter_value skill "$file" || true)"
  if [ -n "${skill:-}" ] && [ -f "$skill" ]; then
    printf '%s\n\n---\n# Loaded skill: %s\n\n%s\n' "$body" "$skill" "$(cat "$skill")"
  else
    printf '%s\n' "$body"
  fi
}

# --- stage runner ------------------------------------------------------------

STAGE_NO=0

# Number of attempts per stage (retries transient API errors like "Overloaded").
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"

# run_stage <agent-file> <output-file> <mode: readonly|mutate> <task-prompt>
run_stage() {
  local agent_file="$1" output="$2" mode="$3" task="$4"
  STAGE_NO=$((STAGE_NO + 1))

  local model sysprompt
  model="$(frontmatter_value model "$agent_file")"
  sysprompt="$(build_system_prompt "$agent_file")"

  echo ""
  echo "=================================================================="
  printf 'STAGE %s: %s\n' "$STAGE_NO" "$(frontmatter_value name "$agent_file")"
  printf '  agent : %s\n' "$agent_file"
  printf '  model : %s\n' "$model"
  printf '  mode  : %s\n' "$mode"
  printf '  output: %s\n' "$output"
  echo "=================================================================="

  # Resumability: a completed stage leaves a non-empty output file. Skip it on
  # re-run (so a mid-pipeline failure can be retried without redoing earlier,
  # non-idempotent stages like the Bug Fixer). Set FORCE=1 to re-run anyway.
  if [ -s "$output" ] && [ "${FORCE:-0}" != "1" ]; then
    echo "--> stage $STAGE_NO SKIPPED: $output already exists (set FORCE=1 to re-run)."
    return 0
  fi

  local -a args=(
    -p "$task"
    --model "$model"
    --append-system-prompt "$sysprompt"
    --permission-mode bypassPermissions
    --add-dir "$ROOT"
  )
  # Read-only agents are hard-blocked from editing code or running shell commands.
  if [ "$mode" = "readonly" ]; then
    args+=(--disallowedTools "Edit" "Bash")
  fi

  local attempt=1 rc=0
  while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
    [ "$attempt" -gt 1 ] && echo "    (retry $attempt/$MAX_ATTEMPTS after transient failure)"
    set +e
    claude "${args[@]}"
    rc=$?
    set -e
    if [ "$rc" -eq 0 ] && [ -s "$output" ]; then
      echo "--> stage $STAGE_NO OK: wrote $output"
      return 0
    fi
    attempt=$((attempt + 1))
    [ "$attempt" -le "$MAX_ATTEMPTS" ] && sleep $((attempt * 5))
  done

  echo "ERROR: stage $STAGE_NO failed after $MAX_ATTEMPTS attempts (exit $rc, output: $output)." >&2
  echo "       Re-run the pipeline to resume from this stage (earlier stages are skipped)." >&2
  exit 1
}

# --- pipeline ----------------------------------------------------------------

echo "Homework 4 — four-agent bug-fixing pipeline"
echo "Working dir: $ROOT"

run_stage "agents/research-verifier.agent.md" \
  "$CTX/research/verified-research.md" "readonly" \
  "Verify the bug research. Read $CTX/research/codebase-research.md, verify every claim against the actual source files, apply the loaded research-quality-measurement skill, and write $CTX/research/verified-research.md with all required sections. Do not modify any source file or the research document."

run_stage "agents/bug-fixer.agent.md" \
  "$CTX/fix-summary.md" "mutate" \
  "Apply the implementation plan. Read $CTX/implementation-plan.md, apply each change to the source exactly, run 'npm test', and write $CTX/fix-summary.md with the required sections (including an explicit Files Changed list)."

run_stage "agents/security-verifier.agent.md" \
  "$CTX/security-report.md" "readonly" \
  "Perform the security review. Read $CTX/fix-summary.md and every file in its Files Changed list, then write $CTX/security-report.md with one entry per finding (severity, file:line, exploitability, remediation) and a summary table. Report only; do not edit code."

run_stage "agents/unit-test-generator.agent.md" \
  "$CTX/test-report.md" "mutate" \
  "Generate and run unit tests. Read $CTX/fix-summary.md, apply the loaded unit-tests-FIRST skill, write FIRST-compliant tests for the changed functions into tests/ledger.changes.test.js, run 'npm test', and write $CTX/test-report.md with the required sections."

echo ""
echo "=================================================================="
echo "PIPELINE COMPLETE — artifacts in $CTX/"
echo "=================================================================="
ls -1 "$CTX"/research/verified-research.md "$CTX"/fix-summary.md "$CTX"/security-report.md "$CTX"/test-report.md
