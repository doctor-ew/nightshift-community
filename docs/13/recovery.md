# Issue 13 recovery record

The retained implementation commits d2929e9, 45bfecb, 2c51e26 and 8dfc146 preceded approved specification and RED seals. They are incomplete attempts, not accepted implementation evidence. Preserve their history. The initial independent missing-task assertion failed against integration baseline 44ad7cc4d6af7a30cde2b139d9ad25c19b41c2bf; subsequent eight-test success covers schema and missing-task checks only.

The dispatcher currently validates a task name without executing a proof gate. The helper lacks challenge and prototype execution, holdout evaluation, complete evidence validation, immutable seal checks and bounded accounting. Existing fixture migration only supplies a task name. It does not establish admissible proof.

Resume with independent specification review, expanded independent RED coverage and recorded seals before further engine implementation. A subsequent seal cannot establish that earlier implementation followed RED-first sequencing. Final delivery must retain this qualification and the actual later verification evidence.

The first specification review incorrectly classified tests/test-behavior-proof.sh as tracked at the integration baseline. Its absence is determined from that baseline Git tree; a concurrent untracked draft is not baseline content. The existing-versus-proposed wording for the GREEN command callsite was corrected in the retained specification.
