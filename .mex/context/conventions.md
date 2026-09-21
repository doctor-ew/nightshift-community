---
name: "conventions"
description: "Project constraints and evidence-focused verification."
triggers: ["convention", "review", "naming"]
edges: [{"target": "context/architecture.md", "condition": "when placing the change in the pipeline"}, {"target": "patterns/edit-trajectory-contract.md", "condition": "when changing recorded evidence"}, {"target": "patterns/preserve-setup-files.md", "condition": "when changing setup writes"}, {"target": "context/stack.md", "condition": "when a convention depends on runtime or tooling constraints"}]
grounds_to:
  - node: function:b081c62f402aaf28c06d252cf11bc392
    fingerprint: mh:64:7b226d696e68617368223a5b31383134343139392c3136373334343133332c373839313932342c33343939333831332c32313639393039362c35303737343134352c353936353238352c373739333737352c32343337313435352c353836333031372c31373931303839362c39393235373031382c38303333313031332c393334363739332c32333535323138342c31323832373832352c3131383537303232312c373535353739342c33373437353736332c3131343234373539362c33383137363739372c3131303639333631392c313830393030342c393832393038372c3136303130373939312c3134353337373332302c38363035333735312c35313532323032362c31323239353839372c313634363838322c34353931313234352c36313130333935382c343431393134332c31303236383738352c323032333531392c3130363433393031322c323739373632382c31303836393338392c35313231333536322c33343138353431362c36353530383733302c353737393338352c31333034363236372c31313232343236322c31313139333936342c37333831343037392c35383039323536372c33333733333134312c37363032383939392c38383330383132342c34363136383631352c3132383434343038302c31383737353335302c36383338373336302c3138343033393938312c37303230383532362c35353339313735312c34353932373938372c31333236303435332c38323333333135372c343533333336322c32343834353935362c373538363439312c31313732363932355d2c226e65696768626f7273223a5b2266756e6374696f6e3a3164636366336661343639393631313637663166626263633231653261386365222c2266756e6374696f6e3a3232383161323162383836363132336239613536643066353663373636306635222c2266756e6374696f6e3a3265656237383439323639386562646165633138343862643933333862633462222c2266756e6374696f6e3a3931666232326166656130663335653833303833386262333139383439643665225d2c22746f6b656e436f756e74223a3536337d
    bodyHash: 6a796f27397f015907ffa4ca0ae866975ee25e23d98e2db3e5dc3a7bd7b7f954
last_updated: "2026-09-20"
mex:
  id: mx_01M21Z3AH9N1C5JA0SSQX67SPF
  type: convention
  status: promoted
  revision: 5
  title: conventions
  relations:
    - type: related_to
      target: mx_01M21Z3ACK0HJ2DDGW0YPPAWKR
      note: when placing the change in the pipeline
    - type: related_to
      target: mx_01M21Z3AYPFXZ88WKFWHCDQ09V
      note: when changing recorded evidence
    - type: related_to
      target: mx_01M21Z3AZH1PBP57Q1V725EMEY
      note: when changing setup writes
    - type: related_to
      target: mx_01M21Z3AV2M2XQ83MT8FJBXV8C
      note: when a convention depends on runtime or tooling constraints
---

# Conventions

<!-- mex:entity
id: mx_01M21Z3AG5T22P4PF1JSHXRHBD
type: convention
status: promoted
revision: 1
-->
## Naming
- Installed artifacts retain the `nightshift-` prefix. Source: `AGENTS.md`, Project conventions.
- Visible task keys name `.nightshift/<task-key>.md` progress files. Source: setup brief, README excerpt.
- Bead IDs are internal, recorded in `docs/<task-key>/.bd-id`. Source: setup brief, README excerpt.

<!-- mex:entity
id: mx_01M21Z3AEWY73YXDX0C04RZ880
type: convention
status: promoted
revision: 1
-->
## Structure
- Canonical stage instructions live in `commands/nightshift-*.md`. Source: `AGENTS.md`, Project introduction.
- Reusable role prompts live in `agents/`; runtime-specific adapters do not replace the core. Source: `AGENTS.md`, Project introduction.
- Supporting execution tooling belongs in `scripts/`; provider/model routing belongs in `routing.json`. Source: `AGENTS.md`, Project conventions.

## Patterns
- Before: adding a static model selection to a shared role. After: represent selection in `routing.json` and keep the role neutral. Source: `AGENTS.md`, Project conventions.
- Before: accepting arbitrary extra trajectory fields. After: update the explicit accepted shape and validation together; [`validate()`](mex://function:b081c62f402aaf28c06d252cf11bc392) rejects unknown fields. Source: `scripts/nightshift-trajectory.py` (line 42).

<!-- mex:entity
id: mx_01M21Z3ADSJ9BPD7RTFEXCZRA7
type: convention
status: promoted
revision: 1
-->
## Verify Checklist
- [ ] Installed names preserve the `nightshift-` prefix; shared roles remain runtime-neutral. Source: `AGENTS.md`, Project conventions.
- [ ] Upstream ticket authority and local beads identity remain distinct. Source: setup brief, README excerpt.
- [ ] Relevant existing fixtures cover the changed boundary; setup and release tests live in `tests/test-setup-ux.py` (line 16) and `tests/test-release-inputs.py` (line 18).
- [ ] Evidence-schema changes retain exact shape checks in `scripts/nightshift-trajectory.py` (line 42).
- [ ] Scaffold claims have sources; behavior-specific grounding uses exact graph facts and all edges resolve. Source: `.mex/local/setup-population-raiHOV/prompt.md` (line 30).
- [ ] Unverified commands, versions, and readiness claims stay marked [TO DETERMINE]. Source: `.mex/local/setup-population-raiHOV/prompt.md` (line 167).
