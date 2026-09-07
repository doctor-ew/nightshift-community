#!/usr/bin/env bash
# nightshift-extractor-meta.sh — metadata for code-fact-extractor runs.
# Outputs: EXTRACTED_AT: <ISO-8601 UTC> and COMMIT_SHA: <short-sha>
# The orchestrator stamps extractor_run into every citation and commit_sha into every
# ## Sources entry, so later drift in a cited file is detectable.
echo "EXTRACTED_AT: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "COMMIT_SHA: $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
