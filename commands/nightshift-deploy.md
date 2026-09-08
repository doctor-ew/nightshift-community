---
name: nightshift-deploy
description: "Deploy stage of the nightshift-* pipeline. Runs tests, bumps version + CHANGELOG, commits, pushes, opens PR, polls CI, then runs a curl-based health check against the deploy URL. No browse daemon, no canary screenshots — just HTTP. Run /nightshift-deploy <task-key> after /nightshift-preflight."
argument-hint: "<task-key> [env]"
---

# /nightshift-deploy — Ship Stage

Final stage of the nightshift-* pipeline. Assumes `/nightshift-preflight` has been run and PREFLIGHT.md exists.
Runs tests → bumps version → updates CHANGELOG → commits → pushes → opens PR → polls CI →
verifies deploy via HTTP health check.

**No gstack.** Does NOT invoke `/ship`, `/land-and-deploy`, `/canary`, or `/health`. The
shape is borrowed; the implementation is local.

---

## Step 1 — Parse arguments and verify preconditions

```bash
PROJECT_CONTEXT=$(python3 "${NIGHTSHIFT_HOME:-$HOME/.nightshift}/scripts/nightshift-project-context.py" --shell) || exit $?
eval "$PROJECT_CONTEXT"
PROJECT="$NIGHTSHIFT_PROJECT_DIR"
TASK=$(echo "$ARGUMENTS" | awk '{print $1}')
ENV=$(echo "$ARGUMENTS" | awk '{print $2}')   # optional: dev|staging|prod (default: configured default)
TASK_DIR=$(bash ~/.nightshift/scripts/nightshift-state-dir.sh --project "$PROJECT" --task "$TASK" --create)
SPEC="${PROJECT}/docs/${TASK}/SPEC.md"
PREFLIGHT="${PROJECT}/docs/${TASK}/PREFLIGHT.md"
DEPLOY_LOG="${PROJECT}/docs/${TASK}/DEPLOY.md"
```

Hard preconditions:
- `$TASK` non-empty (else: `"Usage: /nightshift-deploy <task-key> [env]"` and stop)
- `$SPEC` exists (else: `"No spec — run /nightshift-product first."` and stop)
- `$PREFLIGHT` exists (else: `"No preflight — run /nightshift-preflight $TASK first."` and stop)
- Git working tree exists and is clean of unrelated changes (else: ask "Continue with uncommitted changes? Y/N")
- On a non-default branch (else: ask "You're on $BASE — create a feature branch? Y/N")

---

## Step 2 — Detect deploy config

Look for deploy config in this order:
1. `${PROJECT}/.nightshift/deploy.json` — explicit Nightshift config (preferred)
2. `${PROJECT}/.claude/deploy.json` — legacy compatibility reader; migrate its contents to `.nightshift/deploy.json` when found
3. Resolved project conventions (`docs/PROJECT-CONTEXT.md` in the Nightshift source (installed at
`${NIGHTSHIFT_HOME:-$HOME/.nightshift}/docs/nightshift-project-context.md`)) — read applicable
   deployment instructions, with documented legacy fallback and conflict handling
4. Heuristic detection: `vercel.json`, `fly.toml`, `netlify.toml`, `.github/workflows/deploy*`, `Dockerfile`

`deploy.json` shape:
```json
{
  "platform": "vercel|fly|netlify|gh-actions|docker|custom",
  "default_env": "dev|staging|prod",
  "envs": {
    "prod": {
      "url": "https://example.com",
      "health_path": "/health",
      "expect_status": 200,
      "expect_json": {"status": "ok"},
      "deploy_cmd": "vercel --prod",
      "status_cmd": "vercel ls --json"
    }
  }
}
```

If no config found: ask the user for URL + health path interactively, save to `.nightshift/deploy.json` for future runs.

---

## Step 3 — Run tests

Detect test command from `package.json` scripts (test, test:ci) or pyproject (`pytest`) or
`Makefile` (`test` target). Run it.

```bash
echo "Running tests..."
$TEST_CMD
```

If non-zero: `"DEPLOY_BLOCKED: tests failed. Fix and re-run."` and stop.

---

## Step 4 — Version bump + CHANGELOG

Detect version source: `package.json`, `pyproject.toml`, `VERSION` file, `Cargo.toml`.

Ask: `"Bump version: patch / minor / major / skip?"`

If not `skip`, bump in place. Append entry to CHANGELOG.md under a new heading dated today,
with a one-line summary lifted from the bead title.

```bash
BD_ID=$([ -f "${PROJECT}/docs/${TASK}/.bd-id" ] && cat "${PROJECT}/docs/${TASK}/.bd-id" || echo "")
if [ -n "$BD_ID" ]; then
  TITLE=$(bash ~/.nightshift/scripts/nightshift-capability.sh --has bd \
            && bd show "$BD_ID" --json 2>/dev/null | jq -r '.title' || true)
else
  TITLE="$TASK"  # fallback to the task key itself
fi
# Prepend new CHANGELOG entry
```

---

## Step 5 — Commit

Stage only:
- The bumped version file
- CHANGELOG.md
- Any spec/review/drift artifacts under `docs/${TASK}/` that aren't gitignored

Build commit message:
```
<task-key>: <title>

<one-line summary from bead body>

Refs: <external_ref> (<source>)
```

Commit. Do NOT use `--no-verify`.

---

## Step 6 — Push and open PR

### Production deployment gate

Before the first command that can cause a production deployment (including a
push or merge when the detected platform auto-deploys production), show the
exact target environment, platform, branch/PR, and command. Ask for explicit
confirmation immediately before that command. This is the deploy stage's only
human confirmation gate: do not pause for tests, commits, pushes, PR creation,
or a dev/staging deployment.

```bash
git push -u origin "$(git branch --show-current)"
```

Build PR body from:
- Spec link: `docs/<task-key>/SPEC.md`
- Review summary: `docs/<task-key>/REVIEW.md` (BLOCK/WARN/NOTE counts)
- Drift summary: `docs/<task-key>/DRIFT.md`
- Preflight checklist: `docs/<task-key>/PREFLIGHT.md`
- External ticket link

Open PR. If `gh` is configured for this repo, use `gh pr create`. Otherwise print the
push URL and ask the user to open it manually.

---

## Step 7 — Poll CI

```bash
PR_URL=$(gh pr view --json url -q .url 2>/dev/null)
echo "PR: $PR_URL"
echo "Polling CI..."

# Poll every 30s up to 30 min
for i in $(seq 1 60); do
  STATE=$(gh pr checks --json bucket -q '[.[].bucket] | unique | sort | .[]' 2>/dev/null || echo "unknown")
  case "$STATE" in
    *failure*|*error*|*cancelled*)
      echo "CI_FAILED: $STATE"
      exit 1
      ;;
    "pass"|"success")
      echo "CI_PASSED"
      break
      ;;
  esac
  sleep 30
done
```

If timeout: `"CI_TIMEOUT — surface to engineer, do not auto-merge."` and stop.

---

## Step 8 — Merge

Merge the PR using the configured/default merge strategy. If this merge is the
first action that promotes to production, apply the Production deployment gate
from Step 6 immediately before merging. Otherwise proceed without a separate
approval prompt.

---

## Step 9 — Wait for deploy

If platform has a `status_cmd` (e.g., `vercel ls --json`), poll it for the new deployment
to reach `READY`. Otherwise sleep `${DEPLOY_WAIT_SECONDS:-90}` seconds.

---

## Step 10 — HTTP health check (in lieu of canary)

```bash
URL="${DEPLOY_URL}${HEALTH_PATH}"
echo "Health check: $URL"

for i in 1 2 3; do
  RESP=$(curl -sS -w '\n%{http_code}' "$URL" 2>&1)
  CODE=$(echo "$RESP" | tail -1)
  BODY=$(echo "$RESP" | sed '$d')
  if [ "$CODE" = "${EXPECT_STATUS:-200}" ]; then
    if [ -n "$EXPECT_JSON" ]; then
      if printf '%s' "$BODY" | jq -e ". as \$b | $EXPECT_JSON | to_entries | all(.key as \$k | \$b[\$k] == .value)" >/dev/null 2>&1; then
        echo "HEALTH_OK"
        break
      else
        echo "HEALTH_BODY_MISMATCH: $BODY"
      fi
    else
      echo "HEALTH_OK (status only)"
      break
    fi
  else
    echo "HEALTH_FAIL: status=$CODE body=$BODY"
  fi
  [ $i -lt 3 ] && sleep 10
done
```

Three attempts with 10s backoff. If all three fail: `"DEPLOY_HEALTH_FAILED — investigate."`
and stop. Engineer decides whether to roll back.

---

## Step 10.5 — Post-deploy smoke (Playwright `@smoke`, if any)

The health check proves the server answers; the smoke test proves a real user flow works in a
browser against the **live** deploy. Run the `@smoke`-tagged Playwright subset pointed at
`$DEPLOY_URL`. Zero-cost when the project has no Playwright (`PW_SKIPPED` → treated as pass).

```bash
SMOKE=$(bash ~/.nightshift/scripts/nightshift-pw.sh "$TASK" --run --grep "@smoke" --url "$DEPLOY_URL" \
  --label smoke --out "${PROJECT}/docs/${TASK}/SMOKE-output.log")
echo "$SMOKE"
SMOKE_VERDICT=$(echo "$SMOKE" | grep -oE 'PW_(PASS|FAIL|SKIPPED)' | head -1)
```

- `PW_PASS` / `PW_SKIPPED` → smoke clean; continue to Step 11.
- `PW_FAIL` → the deploy is live but a user-facing flow is broken. Print
  `"DEPLOY_SMOKE_FAILED — live but a @smoke flow is broken. Investigate / roll back."`, record
  it in DEPLOY.md, and stop. This is **post-merge**, so it is an alert, not a gate that can
  un-ship — surface it loudly so the engineer decides on a rollback.

> The `@smoke` tag is a convention: tag the handful of critical-path Playwright tests
> `test('@smoke checkout works', …)`. With no `@smoke` tests, `--grep @smoke` simply matches
> nothing and passes — harmless.

---

## Step 11 — Write DEPLOY.md and update tracker

```bash
cat > "$DEPLOY_LOG" << EOF
## Deploy Log

**Task:** ${TASK}
**Date:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
**Env:** ${ENV}
**Version:** ${NEW_VERSION}
**PR:** ${PR_URL}
**Deploy URL:** ${DEPLOY_URL}
**Health check:** ${HEALTH_RESULT}
**Smoke (Playwright @smoke):** ${SMOKE_VERDICT:-not run}
EOF

TRACKER="${TASK_DIR}/${TASK}.md"
if [ -f "$TRACKER" ]; then
  sed -i '' 's|^- \[ \] /nightshift-deploy.*|- [x] /nightshift-deploy — shipped|' "$TRACKER"
fi
if [ -n "$BD_ID" ]; then
  bd close "$BD_ID" --reason "Shipped: ${PR_URL}" 2>/dev/null \
    || bd note "$BD_ID" "Shipped: ${PR_URL}. Health: ${HEALTH_RESULT}." 2>/dev/null \
    || true
fi
```

Print:
> "Deployed: <env> @ <version>. Health: OK. Bead <task-key> closed.
> Deploy log: docs/<task-key>/DEPLOY.md"
