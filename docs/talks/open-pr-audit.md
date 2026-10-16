# Open pull-request audit

## Snapshot

- Retrieved: 2026-10-14T17:43:26+00:00.
- Repository: `doctor-ew/nightshift-community`.
- Remote `origin/main`: `7bef0f3ed86e1e70b1c454a2abd6af37e4c509f5`.
- Open [PR #132](https://github.com/doctor-ew/nightshift-community/pull/132): `nightshift/community-integrated-20261010` → `main`; head `227328270d8bd98ac3821640e69df7d8c0822b5c`.
- Merged [PR #134](https://github.com/doctor-ew/nightshift-community/pull/134): `nightshift/demo-readiness-133` → `nightshift/community-integrated-20261010`; head `7730fe1b8603d2dd7bfa6d622ed2a0a8b927feb3`; merge commit `227328270d8bd98ac3821640e69df7d8c0822b5c`.
- `origin/main` is an ancestor of #132; #132 contains 16 commits beyond current `main`. #134 is integrated into #132, not into `main`.
- GitHub reports 50 open PRs: #132, 32 other heads already contained in `main`, and 17 divergent heads. Every listed head SHA matches its fetched remote branch.

## Recommendation

1. Treat #132 as the current integration PR. Review and merge that PR through its required checks when authorized; #134 alone does not publish its fixes to `main`.
2. The 32 ancestor-contained PRs below are candidates for closure as superseded. Their exact heads are already in `main`; merging them again is unnecessary. Keep their historical review/evidence references.
3. Review the 17 divergent PRs individually before closure or integration. Their non-ancestor commits also contain patch-unique changes. Ancestry and patch identity alone cannot establish whether their behavior has been superseded by later implementations.
4. Prioritize #131 for deadline-policy reconciliation and #118 for its isolated watcher regression, then audit the older alternate integration branches by diff. Preserve investigation/evidence-only PRs (#51–54) according to the repository retention policy.

## Heads already contained in main and #132

Every row has zero commits beyond #132 by ancestry. Base refs and head SHAs come from the current GitHub PR metadata and fetched remote refs.

| PR | Base ref | Head ref | Head SHA |
|---|---|---|---|
| [#56](https://github.com/doctor-ew/nightshift-community/pull/56) | `nightshift/bounded-convergence` | `nightshift/structural-controller` | `d5b690cf6205e618fad1527af417c947a937245b` |
| [#60](https://github.com/doctor-ew/nightshift-community/pull/60) | `nightshift/structural-controller` | `nightshift/budget-continuation-ui` | `47005ac269af5adb922b99e669e49da69ce6ee3c` |
| [#61](https://github.com/doctor-ew/nightshift-community/pull/61) | `nightshift/budget-continuation-ui` | `nightshift/jev-decisions` | `69763060dfbdac23797434f7172599116ea643f2` |
| [#63](https://github.com/doctor-ew/nightshift-community/pull/63) | `nightshift/jev-decisions` | `nightshift/composable-operations` | `105565ccc71486782bff93976d3987ab6d1b8c76` |
| [#64](https://github.com/doctor-ew/nightshift-community/pull/64) | `nightshift/composable-operations` | `nightshift/operation-console` | `afe619c1c7f116d937a1d0709d60216a9133ae1c` |
| [#76](https://github.com/doctor-ew/nightshift-community/pull/76) | `nightshift/operation-console` | `nightshift/roadmap-source-handoff-66` | `60216ef6a14a67d12128d5c8d7bddb909bd6934f` |
| [#77](https://github.com/doctor-ew/nightshift-community/pull/77) | `nightshift/roadmap-source-handoff-66` | `nightshift/roadmap-foundation-62` | `bad14e5947a040b4794fbae8613bdcf8d8cb73fa` |
| [#78](https://github.com/doctor-ew/nightshift-community/pull/78) | `nightshift/roadmap-foundation-62` | `nightshift/roadmap-self-healing-11-recovered` | `143319d6d88f4ad6eb517b37e2ceeff11aaaf242` |
| [#80](https://github.com/doctor-ew/nightshift-community/pull/80) | `nightshift/roadmap-self-healing-11-recovered` | `nightshift/roadmap-retry-admission-11` | `9d3ba9a23c9f8b0bb36bc7852719cf3d7dd11847` |
| [#84](https://github.com/doctor-ew/nightshift-community/pull/84) | `nightshift/roadmap-retry-admission-11` | `nightshift/roadmap-composition-integrated-67` | `3b8f4f01922b65762a4e32abca10228dd6adce73` |
| [#95](https://github.com/doctor-ew/nightshift-community/pull/95) | `nightshift/roadmap-composition-integrated-67` | `nightshift/roadmap-acceptance-integrated-70` | `6fef11f8c37f8a4b2b19b3ece41d0fa5d0c1d894` |
| [#104](https://github.com/doctor-ew/nightshift-community/pull/104) | `nightshift/roadmap-acceptance-integrated-70` | `nightshift/roadmap-semantic-transport-integrated-68` | `c46f8fc592987621f1753538a45fc5f8207b2011` |
| [#105](https://github.com/doctor-ew/nightshift-community/pull/105) | `nightshift/roadmap-semantic-transport-integrated-68` | `nightshift/roadmap-delivery-reviewed-73` | `13a9abace1286f5274ed1abfc1db5dcd320ee460` |
| [#106](https://github.com/doctor-ew/nightshift-community/pull/106) | `nightshift/roadmap-delivery-reviewed-73` | `nightshift/roadmap-actions-ci-attestation-73` | `a42c3758f8a4bcad5634301040497043dec376d7` |
| [#107](https://github.com/doctor-ew/nightshift-community/pull/107) | `nightshift/roadmap-actions-ci-attestation-73` | `nightshift/roadmap-isolated-runtime-73` | `717e74e06292436442f09d24725a645061f8004b` |
| [#109](https://github.com/doctor-ew/nightshift-community/pull/109) | `nightshift/roadmap-isolated-runtime-73` | `nightshift/roadmap-stage-diagnostics-73` | `689de2987b9b2b7a5aa037cc01b6e5207071d4ec` |
| [#110](https://github.com/doctor-ew/nightshift-community/pull/110) | `nightshift/roadmap-stage-diagnostics-73` | `nightshift/roadmap-optional-recovery-68` | `3c45f8eddb7bd178d1fedb7577697020b2cea027` |
| [#111](https://github.com/doctor-ew/nightshift-community/pull/111) | `nightshift/roadmap-optional-recovery-68` | `nightshift/roadmap-recovery-acceptance-70` | `7478b6b4e1c529c7a7e5792848ece0e3f4bc29d6` |
| [#112](https://github.com/doctor-ew/nightshift-community/pull/112) | `nightshift/roadmap-recovery-acceptance-70` | `nightshift/roadmap-recovery-findings-72` | `9e2fa9440bc7f8d3aee446744c96044c799287bb` |
| [#114](https://github.com/doctor-ew/nightshift-community/pull/114) | `nightshift/roadmap-recovery-findings-72` | `nightshift/roadmap-recovery-progress-70` | `803a07408cb0d1c77b34b49abb2438f19a6352e3` |
| [#115](https://github.com/doctor-ew/nightshift-community/pull/115) | `nightshift/roadmap-recovery-progress-70` | `nightshift/roadmap-reviewer-schema-72` | `788cea6975d91029c2d3d352378cc606ebdd7f9a` |
| [#116](https://github.com/doctor-ew/nightshift-community/pull/116) | `nightshift/roadmap-reviewer-schema-72` | `nightshift/roadmap-review-citation-normalization-72` | `f49264cfee001418dcd65bf231e191bb997e7e51` |
| [#117](https://github.com/doctor-ew/nightshift-community/pull/117) | `nightshift/roadmap-review-citation-normalization-72` | `nightshift/roadmap-assertion-evidence-72` | `946901cb29ae3d3e00aefe3b038af626ca74e333` |
| [#119](https://github.com/doctor-ew/nightshift-community/pull/119) | `nightshift/roadmap-assertion-evidence-72` | `nightshift/roadmap-reviewer-role-coverage-72` | `ef3e1af5ebb51210a92dc798c780a38867cbb785` |
| [#120](https://github.com/doctor-ew/nightshift-community/pull/120) | `nightshift/roadmap-reviewer-role-coverage-72` | `nightshift/roadmap-reviewer-reuse-72` | `83188ff8c1c9643bb22120f3e9d546c2b7181771` |
| [#121](https://github.com/doctor-ew/nightshift-community/pull/121) | `nightshift/roadmap-reviewer-reuse-72` | `nightshift/roadmap-deterministic-evidence-72` | `b2e2847e65ab9ce666cdfcd77a896832dab1397e` |
| [#122](https://github.com/doctor-ew/nightshift-community/pull/122) | `nightshift/roadmap-deterministic-evidence-72` | `nightshift/roadmap-jev-claims-72` | `76cb7aeaa1ee24f40234ce6bca4a5f9f5e09fae2` |
| [#123](https://github.com/doctor-ew/nightshift-community/pull/123) | `nightshift/roadmap-jev-claims-72` | `nightshift/roadmap-operator-escalation-72` | `dc3087787da6d1e22e41db2d5ad3d6509e0ea239` |
| [#124](https://github.com/doctor-ew/nightshift-community/pull/124) | `nightshift/roadmap-operator-escalation-72` | `nightshift/roadmap-token-budget-72` | `307206c67857e2937f78d56c59e5fefa8b855d04` |
| [#125](https://github.com/doctor-ew/nightshift-community/pull/125) | `nightshift/roadmap-token-budget-72` | `nightshift/roadmap-operator-dashboard-72` | `71edd9fe211f001c85831d5b8f398e8ddc00a652` |
| [#126](https://github.com/doctor-ew/nightshift-community/pull/126) | `nightshift/roadmap-operator-dashboard-72` | `nightshift/roadmap-run-estimate-72` | `3b45d2abde20e87d37e9195934fa9c31def8d882` |
| [#127](https://github.com/doctor-ew/nightshift-community/pull/127) | `nightshift/roadmap-run-estimate-72` | `nightshift/roadmap-interrupted-resume-72` | `8cc09aaf0b883dc04c418e29b05a80dd4d0f43cb` |

## Divergent heads

“Unique” counts non-ancestor, non-patch-equivalent right-side commits from `git rev-list --right-only --cherry-pick --count #132...head`. No divergent row is already contained in `main`.

| PR | Base ref | Head ref | Head SHA | Unique commits |
|---|---|---|---|---:|
| [#22](https://github.com/doctor-ew/nightshift-community/pull/22) | `main` | `docs/13-behavioral-proof-design` | `1b0eff4e003f303475a462929bbd01ab1e98ba41` | 1 |
| [#42](https://github.com/doctor-ew/nightshift-community/pull/42) | `main` | `fix/nightshift-init-staged` | `c3b77a65f6ec477a6ddb45839b791ccea2ece64f` | 1 |
| [#43](https://github.com/doctor-ew/nightshift-community/pull/43) | `nightshift/developer-onboarding` | `fix/nightshift-unattended-permissions` | `dafc9830aa2dd4c548d484778092218a006353b0` | 1 |
| [#51](https://github.com/doctor-ew/nightshift-community/pull/51) | `nightshift/developer-onboarding` | `nightshift/retained-onboarding` | `0d7d452fcf9dccc379aa3de55ecedb62b966b2bf` | 1 |
| [#52](https://github.com/doctor-ew/nightshift-community/pull/52) | `main` | `nightshift/retained-ticket-35` | `33df7b28b17dce1936efbb29311a53cfea356693` | 3 |
| [#53](https://github.com/doctor-ew/nightshift-community/pull/53) | `main` | `nightshift/retained-ticket-46` | `489c69d6db1b91fa41eeb3ef4f57977bc939c742` | 1 |
| [#54](https://github.com/doctor-ew/nightshift-community/pull/54) | `nightshift/bounded-convergence` | `nightshift/retained-convergence-evidence` | `aceabf4d49e9e8255207df8f90c8083b1374627b` | 1 |
| [#55](https://github.com/doctor-ew/nightshift-community/pull/55) | `nightshift/bounded-convergence` | `nightshift/installed-repairs` | `c252742f25892eabb774a7fe33cb323bfcf06083` | 6 |
| [#57](https://github.com/doctor-ew/nightshift-community/pull/57) | `nightshift/installed-repairs` | `nightshift/codex-first` | `814430815bcdc1afcda8ecc19124f35b63a845fe` | 6 |
| [#82](https://github.com/doctor-ew/nightshift-community/pull/82) | `nightshift/roadmap-self-healing-11-recovered` | `nightshift/roadmap-work-packages-67` | `b32e19d461693b9dd3746ef1554a87bb4cf040dd` | 10 |
| [#83](https://github.com/doctor-ew/nightshift-community/pull/83) | `nightshift/roadmap-work-packages-67` | `nightshift/roadmap-package-hardening-67` | `17caf67f04d80c0c271f41bf1f135ecb19890acc` | 13 |
| [#85](https://github.com/doctor-ew/nightshift-community/pull/85) | `nightshift/roadmap-package-hardening-67` | `nightshift/roadmap-package-drafting-67` | `44309fbdf018d05b0c5232a4eeca20aa547a1238` | 16 |
| [#96](https://github.com/doctor-ew/nightshift-community/pull/96) | `nightshift/roadmap-semantic-provenance-68` | `nightshift/roadmap-typed-unittest-72` | `c634e61f0429c9574204bad9c095f73d00b27ee4` | 4 |
| [#99](https://github.com/doctor-ew/nightshift-community/pull/99) | `nightshift/roadmap-decision-retention-70` | `nightshift/roadmap-assessment-context-70` | `0e11d297e318a923fae8a29d303f9c3f3e90576d` | 7 |
| [#102](https://github.com/doctor-ew/nightshift-community/pull/102) | `nightshift/roadmap-assessment-context-70` | `nightshift/roadmap-semantic-launcher-68` | `ec905c4d626aa5fab60a8a48a3785b224f6e97a2` | 9 |
| [#118](https://github.com/doctor-ew/nightshift-community/pull/118) | `nightshift/roadmap-assertion-evidence-72` | `nightshift/roadmap-dashboard-watcher-race-72` | `38c3e0e3683923215f584ae7a50457c7c36f312b` | 1 |
| [#131](https://github.com/doctor-ew/nightshift-community/pull/131) | `main` | `nightshift/evidence-driven-completion` | `0b5077ed8acfc9163b019745a8f53316e6b668df` | 1 |

## Evidence and boundary

Commands: `gh pr list --state open --limit 100 --json number,title,headRefName,headRefOid,baseRefName,url`; `gh pr view 132 --json number,state,baseRefName,headRefName,headRefOid,mergeCommit,url`; the same view for #134; `git fetch --no-tags origin`; exact remote-ref resolution; `git merge-base --is-ancestor`; `git rev-list --count`; and patch-equivalence counts above.

This audit covers commit ancestry and PR status. It does not certify feature behavior, current CI, or release deployment. No PR was merged, closed, rebased, or retargeted during the audit. The working branch was not switched.

This snapshot precedes the talk-deck review PR. Counts describe the audited backlog, not future PR additions.
