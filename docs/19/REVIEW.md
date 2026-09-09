# Issue 19 review

Status: independent review and dynamic verification PASS; hosted CI remains required before merge.

The specification was independently reviewed and sealed at d85b16a. Independent meaningful RED was sealed at a67d848. Review identified a further component-order symlink defect; an additional independent RED regression was bot-sealed at 6343bc4 before repair. Original assertions remain intact.

The first focused suite run found two behavioral failures, then all 15 cases passed after repair. All 34 offline suites passed. The additional symlink regression initially reproduced a false-clean audit, then all 16 cases and alias-preservation fixtures passed after component-preserving resolution. The retained complete CLI reproduction now fails with an external-path coverage diagnostic.

Independent static installer review found unchecked category serialization and inventory validation before uninstall. Both were repaired and rechecked. The drift review found inconsistent explicit-root canonicalization; the shared module now resolves roots consistently with the scanner.

Real copy and symlink installations into isolated temporary targets passed installation and audit, including a repaired-scanner refresh. The installed copy also executed its adjacent helper and audited all 154 owned files successfully. Active user installation and Coach were not modified.

The first cross-provider code reviewer could not execute scripts under its CLI permissions. Its static approval did not satisfy the authoritative gate after the independently reproduced symlink defect. That review attempt remains charged substantive; the focused independent repair review approves subject to dynamic GREEN, now satisfied by the final 16-case run against recorded source hashes. Source-policy exceptions remain exact and reviewed; no automatic baseline acceptance was used.

Full offline logs remain under /private/tmp/nightshift-19-offline. Focused failures, repairs, ownership audit results and budget attempts are retained in this task directory. A separate exact-source relative-symlink audit also passes. ShellCheck and hosted CI remain required before merge.
