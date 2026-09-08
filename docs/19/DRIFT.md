# Issue 19 independent static drift review

Result: PASS — the root-normalization finding is repaired in the reviewed source. Static review only; no tests executed and no active installation inspected or changed.

Baseline: 20aefa116003134f6464b2673ab11f8a06e9e353. Scope authority: sealed docs/19/SPEC.md in the managed issue 19 checkout.

## Resolved finding

Original P2: Shared installation roots and audit roots have different normalization. scripts/nightshift-install-inventory.py:16-17 uses os.path.abspath for target roots, retaining symlink spelling. The installer persists those generated destinations into install-links.json. scripts/nightshift-branding.py:501-504 resolves the same explicit target roots physically before generating its expected inventory; lines 424-427 require exact destination/source string equality.

Consequently an installation through a symlinked root, including /tmp versus /private/tmp on macOS, generates a valid ownership record that its own subsequent audit rejects as invalid_ownership. Copied artifacts then become unknown ownership; symlink artifacts may still be read independently, but coverage remains failed. This contradicts the declared support for explicit canonicalized roots and copy/symlink installation correspondence. Repair verified: the shared module now uses Path(targets[key]).resolve() at lines 16-17, matching the scanner. Installer operations and persisted record keys therefore use the same physical roots as audit expectations. This finding follows directly from the code paths; no dynamic reproduction was run in this review.

## Scope and preserved behavior

Changed production files are exactly the approved install.sh, scripts/nightshift-install-inventory.py, scripts/nightshift-branding.py, scripts/nightshift-branding-policy.json and docs/BRANDING-AUDIT.md. Tracked changes additionally include approved docs/19/SPEC.md and tests/test-branding.sh. Test contents were not inspected. Untracked docs/19 review inputs/receipts are stage evidence. The checkout also contains untracked .nightshift.toml and scripts/__pycache__; these are not approved production changes and should remain outside the implementation commit. Their presence does not establish which process created them.

Static mapping comparison retains baseline Claude commands, shared shell/Python/jq helpers, contracts, roles, routing, manifest, optional dashboard tree/server, legacy Claude adapters and project-context helper, Codex skill tree, launcher, and the renamed installed project-context documentation. Additions are the two prefixed Python helpers and scanner policy in shared scripts. Category ordering retains the existing stages and local continues using the Codex skill mapping.

The installer check branch exits before timestamp generation, dependency probes, directory/conflict operations, hook reads, update configuration and installation. The normal installer consumes the shared mapping. The previously reported unchecked serialization and uninstall dependency defects are repaired: serialization completes with checked status before consumption, and uninstall exits before mapping generation.

No baseline changes appear in agents/, commands/, routing.json, nightshift.toml, scripts/nightshift-project-context.py, scripts/nightshift-capability.sh, scripts/nightshift-agent.sh, scripts/nightshift-factory.sh or docs/SCOPED-VERIFIER.md. The precise exception policy preserves the integrated convention resolver and actual dispatcher contexts. No source diff indicates a routing, authentication, or issue 18 runtime behavior change beyond installer mapping integration.

## Limits

This review cannot certify absence of activity outside the checkout. It made no Coach or active-home reads and performed no installation, provider dispatch, dynamic test or filesystem mutation except writing this report. Dynamic no-read/no-write assertions, all-runtime installed audits and regression pass results must come from the execution receipts. The normalization finding is resolved statically; the parent is separately validating an actual alias-root install/check.
