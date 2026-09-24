# Product scope review — attempt 2

## Verdict

REQUEST CHANGES. The returned draft does not preserve the required scope of GitHub issue 35. No implementation or publication gate is passed.

## Findings

| Required behavior | Draft gap | Required repair |
| --- | --- | --- |
| Source/repository/ticket identity | Uses external reference without repository namespace | Bind all three identity components |
| Available provider and orchestrator usage | Defers Codex usage and orchestrator capture | Capture verified structured receipts; retain unknown only for unavailable observations |
| Cached token categories | Restricts tokens to input and output | Preserve fresh, cache-read, cache-write, output, and explicit total semantics |
| Reported cost | Every cost field is unconditionally unknown | Retain available reported estimates and their provenance; actual billed amount stays distinct |
| Parent/child overlap | Splits subtotals without establishing whether usage overlaps | Define receipt coverage and avoid adding overlapping observations |
| Persistent JSON report | Proposes index plus ephemeral read-only report | Persist an atomic report reconstructable from immutable receipts |
| Interrupted/resumed events | Prefers possibly stale summary whenever present | Rebuild from authoritative retained receipts, including newer events |
| Acceptance criteria | Replaces upstream criteria with weaker criteria | Preserve all eight upstream criteria |

## Evidence

The unapproved draft and its provider-authored proposal are retained with the normalized attempt-2 receipt. The original upstream requirements are retained in ticket.json. The final repair brief identifies each gap and includes verified primary-source provider formats.
