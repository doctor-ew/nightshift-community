# Codex controller integration

Integrated the normalized Codex proposal. Controller changes before independent review: reordered scope table columns for installed parser; clarified receipt ingestion/provider parser CLI and normalized receipt fields; reconciled test extension wording; removed false base-commit citations for untracked delivery artifacts. Provider authorship remains Codex; Claude review must cover the complete resulting artifacts.

## GREEN component integration
Codex gpt-5.6-sol authored the parser and runtime integration proposals in implementation-parser.out.json and implementation-integration.out.json. The controlling Codex session applied their artifacts.diff content without source changes. Workers remained read-only and did not execute tests. Bash syntax validation passed for the three changed shell scripts. Core accounting remains pending.

Integrated subsequent Codex component and repair proposals. Only patch-format headers were normalized; no controller production-source edits. Added controller-owned offline dispatcher integration fixture under docs/35; it covers numeric epochs, real shell binding, pricing provenance and both providers. Routing remains outside delivery scope.
