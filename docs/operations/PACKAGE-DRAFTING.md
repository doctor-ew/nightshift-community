# Bounded package artifact drafting

## Behavior

A parent operation plan can select the optional version 1 `package_draft`
descriptor. It declares 2–16 child slots, a template file, composition ceilings
and a maximum draft size of at most 65,536 bytes. The controller derives four
owned paths per slot: the operation plan, specification, scenarios and Python
checks. Source implementation scope remains separate.

Ordinary Groom authors those artifacts and the parent graph/scenarios. The
worker receives the exact inventory and template. The template pins child limits,
aggregate allocation, environment and independent review policy. Child plans
cannot expand source ownership, replace parent request/rules/architecture, nest
another draft or authorize publication. Composition ceilings come from the
operator-approved descriptor, not the generated graph.

The controller applies the proposed patch in a disposable overlay, validates the
complete graph and every child plan/scenario, checks source ownership, template
policy, requirement coverage and Python syntax, and enforces the byte cap before
writing parent files. This validation runs during execution, completed-worker
recovery and checkpoint finalization. Invalid candidates leave parent artifacts
unchanged. Source bytes and existing file modes are preserved, including CRLF.

Independent Groom challenge receives all generated child contracts and checks.
Structural validation never substitutes for semantic challenge. A rejected
challenge retains the draft and grants no child execution authority. Successful
preparation still requires the existing separate composition authorization.

## Entry points and limits

The shared operation and package CLI/browser entry points are unchanged. Package
preparation can start with an empty child list and no child artifacts; a seed graph
still supplies the explicit parent reference and initial bounded allowance.
Selecting a descriptor does not start a provider or grant authority.

The initial profile uses fixed, explicitly selected child slots and Python check
files. It does not infer repository ownership or allow arbitrary output paths.
Concurrency, general interruption reconciliation, guided intake and delivery
endpoints remain separate roadmap work. Graph success means a reviewed isolated
integration workspace pending manual acceptance. No installed runtime or live
provider certification is implied.

## Verification boundary

Synthetic tests start without child artifacts, draft a split, independently
challenge it, run the existing composition and replay without another draft.
Independent tests cover candidate rejection, protected paths, budgets, policy,
size/hash integrity, stale templates, worker recovery, partial parent integration,
operator drift and exact CRLF/mode preservation. Actual browser tests use
synthetic executable providers and disposable repositories.

Independent review approved draft validator SHA-256
`091ca3885cc32663efa0064a210ce2b363c735094ba2205720044fc2232313f2`
and operations SHA-256
`64fdc91010b7c52a20f6891b675c9365703643c1a5005289aae6d43ec637a195`.
Twelve independent cases passed in 8.382 seconds; three author cases passed in
24.832 seconds. All 24 existing operation cases passed in 86.145 seconds.
ShellCheck passed the new test wrapper. Earlier runs overlapping source edits invalidated their bindings
and are superseded, not passing final evidence.

At code revision `bdeb1146aecf300a89b0305fcb57f79307df7673`, actual Chromium
153.0.8010.12 and launcher parity produced 14 synthetic executable calls, 27,907
packet bytes and 5.070853500990779 measured worker seconds. Replay added zero
calls. Unknown calls and remaining reservations were zero. The exact request
sizes and source hashes are in `PACKAGE-DRAFTING-VALIDATION.json`. Provider token
usage, provider-cache consumption and billing remain unknown; no quality or cost
savings claim follows from these fixtures.

Temporary installation of that exact code revision passed in 14.413 seconds.
This is foundation launcher/dashboard installation evidence, not installed
package-browser or live certification.

Convention checks: installed names retain the prefix; roles remain neutral;
upstream references and local identity remain distinct; existing operation and
new package fixtures cover the boundary; the trajectory schema is unchanged;
scaffold claims cite source files while graph-index grounding remains unavailable;
unsupported endpoints and live readiness remain explicitly unverified.
