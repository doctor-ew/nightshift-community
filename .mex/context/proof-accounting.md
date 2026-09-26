---
name: "proof-accounting"
description: "Proof admission, pinned policy, and accounting invariants."
triggers: ["proof", "budget", "pending attempt"]
edges: [{"target": "context/architecture.md", "condition": "when placing the change in the pipeline"}, {"target": "context/conventions.md", "condition": "when implementing or verifying changes"}, {"target": "patterns/debug-proof-budget.md", "condition": "when proof admission fails"}]
last_updated: "2026-09-26"
mex:
  id: mx_01M21Z3AMXY4C5AAH2N44827A3
  type: architecture
  status: promoted
  revision: 4
  title: proof-accounting
  grounds_to:
    - node: function:8bb03e0dafe7429342393c57fd98549a
      fingerprint: mh:64:7b226d696e68617368223a5b31383134343139392c3230313133313739322c33313734393735322c3138383430363032342c32383432333736312c35393439383430392c373535393336342c35353836353739332c31393235343436362c39373635373536302c343136333032372c31313236353438362c38393937393033362c35323931303230312c3131343038313931342c31333333333631352c35353838323732362c38363137383938382c34353839353537392c39303537353339372c32363739393238352c37343532313133312c313830393030342c39323437363338312c3130383537373034382c35383030393032342c31353235393235332c3230353730303639302c33313135313235312c333038333636392c38353335323039392c37353034303530312c35353037333938302c3130363631303637342c3136303431313632362c3130303233363535362c323232363838322c31303836393338392c32303431373732342c3131393039353337302c38333238373839342c37303933393435302c39303031373634392c33393031383339342c383930363633302c31333838323738372c35383039323536372c3131363935363737372c3134323533363834312c33373736333238382c33373232383730352c33313931383334322c3138393431313031362c32353237373831332c35383133363132322c37303230383532362c35343139343937332c39313732363031382c31333236303435332c31303831393534332c31323330333835362c3638373833303739322c36313336393637312c31313732363932355d2c226e65696768626f7273223a5b2266756e6374696f6e3a3464646332386465626462353032393134373932643861306163313331326163222c2266756e6374696f6e3a6264373365613135393235666639323162633265616334343966343832356432222c2266756e6374696f6e3a6435663264346336643230353930643866656539646333316131623333666232225d2c22746f6b656e436f756e74223a3134347d
      bodyHash: 583ef1bbd3e5bd9bfe959db933eb6ef79ca8a1638f1ea5af78fd51c3903902c4
    - node: function:bd73ea15925ff921bc2eac449f4825d2
      fingerprint: mh:64:7b226d696e68617368223a5b31383134343139392c33373631303838352c373839313932342c33343437313534392c34363932353136342c33303133353032342c3133313932322c31303134363434322c31393235343436362c383835343539312c373030313839342c31313236353438362c31303336313937372c35323931303230312c32383331363038322c353231353134362c35353838323732362c31383232353833342c3130323035393839352c373039333136302c323837303330302c37343532313133312c313830393030342c32313037353633352c32373832323037342c363835383330332c31373332303832392c37363838313430302c34343832353431322c313634363838322c323038333831392c32303731383530392c343431393134332c33313331373435362c31393737313632362c32363038343030352c37383639343034302c373431373337312c35363936323936392c353332323233322c333739373038362c33303639373736312c363735313632382c31303934373736382c333831343234382c343439393438302c333731323733372c313837383932312c37363032383939392c32333031303230362c35383035333630332c3132323033363630342c31333437383834372c31373437313931302c31323735333830342c33343137383631392c32323530313439382c33373033383830302c31333236303435332c33333736303932372c31323330333835362c32343834353935362c3539373436322c31313732363932355d2c226e65696768626f7273223a5b2266756e6374696f6e3a3862623033653064616665373432393334323339336335376664393835343961225d2c22746f6b656e436f756e74223a3731397d
      bodyHash: 35b02837212053fb2d2961a35005fd58ad4b46c6e12fad13853408bb97acaf31
    - node: function:d5f2d4c6d20590d8fee9dc31a1b33fb2
      fingerprint: mh:64:7b226d696e68617368223a5b39343930313136302c3132313639323530362c33313734393735322c36343236323035362c33303331313432322c34393639353634392c3133313932322c37383837343238352c33383330333439312c383835343539312c31373931303839362c31313236353438362c37323039333639302c35323931303230312c343831303535372c3130393434393032372c3131383537303232312c383339303930342c37333334333330372c3131393132353134332c31393031393432382c3134363637383139392c313830393030342c38383838343630342c3133353837333037312c38353335393234352c31373332303832392c3132343236313330352c38313537333137382c313634363838322c38353335323039392c34343632363535362c3132333030393735322c3137373837313339322c36343138343337372c3233393432393431372c32373230343131352c38373632353937392c35363936323936392c33343138353431362c34353230313436322c37303933393435302c34393038353338382c36363138333530322c31383434303833372c393232333838372c36383337343337332c3130323137353135312c36343137333237362c39323931333838322c33303336353434372c37333535363435332c36313738363837332c3135333333313635302c31383334323430392c34383933333933332c35343139343937332c38333334333434352c31333236303435332c37333335383338332c33333632323833352c3132333232393037362c31373734323934342c31313732363932355d2c226e65696768626f7273223a5b2266756e6374696f6e3a3464646332386465626462353032393134373932643861306163313331326163222c2266756e6374696f6e3a3862623033653064616665373432393334323339336335376664393835343961225d2c22746f6b656e436f756e74223a3131377d
      bodyHash: caa9036bad63922d14d879641de0b480e65c944b99a926aa3fe36a0fde1404c1
  relations:
    - type: related_to
      target: mx_01M21Z3ACK0HJ2DDGW0YPPAWKR
      note: when placing the change in the pipeline
    - type: related_to
      target: mx_01M21Z3AH9N1C5JA0SSQX67SPF
      note: when implementing or verifying changes
    - type: related_to
      target: mx_01M21Z3AXS7SE70JP7YXVEKTBJ
      note: when proof admission fails
---

# Proof Accounting

## State and validation
[`proof_budget()`](mex://function:8bb03e0dafe7429342393c57fd98549a) initializes policy, pin status, attempts, gate reservations/launches, infrastructure failures, and repairs. A changed policy is rejected once pinned. Source: `scripts/nightshift-retry-budget.py` (line 139).

[`proof_validate()`](mex://function:bd73ea15925ff921bc2eac449f4825d2) requires exact budget keys and derives counters from attempt records. Gates are development/final; kinds are prototype/challenge/probe; outcomes are pending/pass/fail/unknown. Probes do not reserve calls and must remain unlaunched with unknown outcome. Unknown outcomes contribute to infrastructure failures. Source: `scripts/nightshift-retry-budget.py` (line 154).

## Admission boundary
[`proof_admit()`](mex://function:d5f2d4c6d20590d8fee9dc31a1b33fb2) rejects pending attempts, exhausted infrastructure allowance, or reservations plus minimum exceeding gate calls. Admission alone does not launch a worker or prove task completion. Source: `scripts/nightshift-retry-budget.py` (line 202).

## Bounds
The validated proof policy allows 1–64 calls per gate, 0–64 repairs and 0–2 infrastructure failures, 1–120 timeout seconds, and 1–1048576 output bytes. These proof limits must not be conflated with the setup manifest's stage repair budgets. Sources: `scripts/nightshift-retry-budget.py` (line 162), `scripts/nightshift-setup.py` (line 38).

## Registered repair recurrence

The source dispatcher stores canonical registered-artifact signatures per attempt and refuses a signature previously finalized as substantive. Restart, formatting, finding-ID and output-name changes cannot reset admission. Pending and infrastructure outcomes retain their separate handling. This is source-review accounting, separate from proof-call accounting. Sources: `scripts/nightshift-retry-budget.py` (`repair_admission`, `run_dispatch`), `tests/test-repair-dispatch.py`.

Package composition wall follow-up: later authorizations, including a different operator or graph binding, cannot exceed the earliest retained composition deadline. Idle before the first composition authorization retains the active preparation policy. Sources: `scripts/nightshift-package-controller.py` (`Packages.authorize`), `tests/test-package-composition-window-review.py`, `docs/operations/COMPOSITION-WINDOW.md`. Synthetic evidence only; no live activation.
Semantic cache identity follow-up: evaluator/mapper/configuration-adapter/transport source hashes bind semantic authority and are revalidated with the current task, policy and route. Changed code requires fresh calls within retained budgets; old receipts cannot be relabeled. Sources: `scripts/nightshift-operation-decisions.py`, `tests/test-semantic-cache-review.py`, `docs/operations/SEMANTIC-CACHE-IDENTITY.md`. Other typed mapping acceptance remains open.

Semantic provenance follow-up: operation-owned paths constrain evidence roles, each obligation requires complete context/case coverage, and independent escalation must return explicit evidence/requirement/finding identifiers. Raw malformed/partial outputs remain retained with charged calls. Sources: `scripts/nightshift-operation-decisions.py`, `tests/test-semantic-provenance-review.py`, `docs/operations/SEMANTIC-PROVENANCE.md`. Synthetic only; no live accuracy or savings claim.

Typed verification candidate: optional `unittest-v1` checks use trusted lifecycle observations, not printed summaries. Effective environment, interpreter/unittest identity and adapter/supervisor code are bound; raw partial/oversized evidence is retained while bounded projections fail explicitly. Existing wrappers remain `legacy-log-v1`. Sources: `scripts/nightshift-verification.py`, `scripts/nightshift-unittest-runner.py`, `tests/test-typed-verification-review.py`, `docs/operations/TYPED-VERIFICATION.md`. Synthetic only; downstream integration/live certification remain separate.
