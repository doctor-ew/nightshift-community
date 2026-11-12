#!/usr/bin/env bash
set -uo pipefail
# Task certification must fail when the checkout-only live record is absent.
export NIGHTSHIFT_REQUIRE_INSTALLED_ACCEPTANCE=1
# Normalize platform aliases before allocating isolated test directories.
export TMPDIR="$(cd "${TMPDIR:-/tmp}" && pwd -P)"
result=0
# C-1/C-7/C-8: inventory, actual installed acceptance, public claims.
python3 docs/154/run-release-certification.py || result=1
# C-2/C-4/C-6/C-9: source identity, typed receipts, resume and eligible actions.
python3 tests/test-pipeline.py || result=1
bash tests/test-factory-preflight.sh || result=1
# C-3/C-5: worker/direct scope and authentication/authorization boundaries.
bash tests/test-factory-auth.sh || result=1
python3 tests/test-ticket-budget.py || result=1
python3 docs/154/inventory-route-check.py || result=1
python3 docs/154/routing-resume-check.py || result=1
python3 docs/154/certification-mode-check.py || result=1
exit "$result"
