# Installation reconciliation

The installation branch integrates the convergence and console recovery changes from `7fca93b`, initialization staging isolation from `c3b77a6`, and unattended Claude write-worker dispatch from `dafc983`. The branding policy now matches the exact routed executor lines, including the isolated read-only source reader.

Verification: initialization suite (10 tests), dispatcher suite (134 assertions), and branding/install ownership suite (16 tests plus installer ownership checks) pass. Console recovery and launcher regressions are recorded separately before activation. These checks do not establish ten-minute live specification delivery.

The operator's original checkouts and ticket evidence remain intact. Existing installation configuration bytes are preserved; links to the previous checkout are retained in a private installation backup. Credentials and private configuration are not included in this document.

Publication inventory: PR 50 contains convergence/recovery; PRs 51–54 preserve previously unpublished onboarding, ticket 35, ticket 46, and convergence evidence. Those preservation PRs are drafts and are not delivery certification. The broader deterministic factory controller is a separate implementation under review.

Activated revision: `72dd0f5f61e5b8c5e2fcce174c9fac9bb1f61615`. The actual source and installed audit passes with 235 installed artifacts, no missing/unknown/unreadable entries, and no findings. Receipt: `docs/installation-audit-72dd0f5.json`. The launcher regression also passes. The installer repair now retains ownership mappings for preserved regular configuration files; the regression verifies byte preservation and a complete post-repair audit.
