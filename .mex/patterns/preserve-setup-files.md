---
name: "preserve-setup-files"
description: "Preserve private file semantics when editing setup"
triggers: ["setup writes", "manifest persistence"]
edges: [{"target": "context/conventions.md", "condition": "when implementing and verifying this change"}, {"target": "context/setup.md", "condition": "when understanding the relevant subsystem"}]
last_updated: "2026-09-08"
mex:
  id: mx_01M21Z3AZH1PBP57Q1V725EMEY
  type: pattern
  status: promoted
  revision: 3
  title: preserve-setup-files
  grounds_to:
    - node: function:365c32709a8f7d26a4a7e4663e5a8274
      fingerprint: mh:64:7b226d696e68617368223a5b31383134343139392c39333530313135362c38323430323834372c333534353038352c31323035313133392c37363839323333362c34313735343830312c36333537323330352c32353331383030302c31313130393635372c3339323234372c333831333136362c31373431353239352c35323931303230312c38333638393339322c37393138393236332c3131383537303232312c383339303930342c39353933303538332c31333438373734382c3233313730323533322c35313430373133342c313830393030342c3133343232353733372c39373435303534342c38353335393234352c37333230343038392c35333630343931312c3138373233373630332c32313435343331332c36303230353338372c3132333738353538322c343431393134332c363535333433312c35333435323433352c3132353633373736312c3131303731353836362c31303836393338392c35363936323936392c33343138353431362c3433383236303036352c32353337303631302c373036313535342c32343334373132342c3134303639323935332c3132393138363339382c35383039323536372c3132333334313832322c3130393038363238322c32323934333537332c33303336353434372c3134353331333732372c3139383238343837352c3133393832373932312c3133323139363139382c37383932363934362c35373231353235322c3138333435373037372c3133323539373539362c35303733303035362c31353837363939342c37373637393735362c32333032383630312c31313732363932355d2c226e65696768626f7273223a5b227661726961626c653a3863363062643634623836346263646138623539613336343331626536366337225d2c22746f6b656e436f756e74223a3130307d
      bodyHash: bba76a27bc9fa520d2a97e9e9dea81973545d0ac440922e8aaa568cc103f316e
  relations:
    - type: related_to
      target: mx_01M21Z3AH9N1C5JA0SSQX67SPF
      note: when implementing and verifying this change
    - type: related_to
      target: mx_01M21Z3AT5N7R4NW7K2G93Q8K4
      note: when understanding the relevant subsystem
---

# Preserve private file semantics when editing setup

## Context
Load setup context. [`private_file()`](mex://function:365c32709a8f7d26a4a7e4663e5a8274) is the private temporary-file boundary in setup. Source: `scripts/nightshift-setup.py:146`.

## Steps
1. Keep configuration edits in `scripts/nightshift-setup.py`; load its graph neighborhood before changing scalar handling. Source: `scripts/nightshift-setup.py:1`.
2. Preserve project-local temporary creation and owner-only mode masking in [`private_file()`](mex://function:365c32709a8f7d26a4a7e4663e5a8274). Source: `scripts/nightshift-setup.py:147`.
3. Preserve flush and fsync before returning the temporary path. Source: `scripts/nightshift-setup.py:151`.
4. Extend existing setup fixtures for any changed prompt/default behavior. Source: `tests/test-setup-ux.py:29`.

## Gotchas
Existing source mode is masked with 0600; do not replace this with broader permissions. Regression fixtures also preserve existing comments and custom repair budgets. Sources: `scripts/nightshift-setup.py:149`, `tests/test-setup-ux.py:52`.

## Verify
- [ ] Run `python3 tests/test-setup-ux.py`. Source: `tests/test-setup-ux.py:16`; invocation verified during population.
- [ ] For a persistence change, verify owner-only temporary permissions and durable write behavior in a temporary project. Source: `scripts/nightshift-setup.py:146`.

## Debug
Use the fixture's patched argv/input/TTY harness to distinguish prompt regressions from persistence regressions. Source: `tests/test-setup-ux.py:17`.

## Update Scaffold
- [ ] Update `.mex/ROUTER.md` if project state changed.
- [ ] Update affected `.mex/context/` files and grounding after behavior changes.
- [ ] Update `.mex/patterns/INDEX.md` when adding a task pattern.
