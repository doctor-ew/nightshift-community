---
theme: default
title: Nightshift
info: Skills, routing and evidence for agentic engineering
colorSchema: dark
aspectRatio: 16/9
canvasWidth: 1280
fonts:
  sans: Source Code Pro
  serif: Source Code Pro
  mono: Source Code Pro
  local: Source Code Pro
drawings:
  persist: false
transition: none
mdc: true
---

<div class="slide-number">NIGHTSHIFT</div>

# Nightshift

<div class="hero-sub">Skills, routing and evidence<br>for agentic engineering</div>

<div class="tagline">Drew Schillinger</div>

<div class="source">Community harness demonstration</div>

<!--
Introduce Nightshift as a source-agnostic engineering workflow. Today we will inspect the skill, canonical instructions, provider routing and actual controller evidence. The demonstration is a small public task, not a claim about every software project. Source: AGENTS.md; README.md. Speaker name: supplied GSU slide reference.
-->
---

<div class="slide-number">OVERVIEW</div>

# Completion needs evidence

<div class="two"><section><h3>The worker returns</h3><p>A provider finishes its process.</p><p>A structured response records its result.</p></section><section><h3>The controller checks</h3><p>Tests and required proof pass.</p><p>Current receipts bind to the task, source and stage.</p></section></div>

<div class="takeaway">A successful process exit alone cannot complete the ticket.</div>

<div class="source">scripts/nightshift-pipeline.py</div>

<!--
Give the concrete example from the rehearsal: Implementation produced working code and GREEN tests, but its receipt included an expected RED exit 1 among required successful checks. The controller rejected that receipt. A later attempt validated the retained evidence correctly; it did not rewrite the old failure. Source: docs/133/IMPLEMENTATION.md; commands/nightshift-implement.md.
-->
---
src: ./shared-core.md
---

---
class: closing
---

<div class="slide-number">NIGHTSHIFT</div>

# Nightshift community

<p class="big">The canonical workflow and routing live in the repository.</p>

<p class="repo-link"><a href="https://github.com/doctor-ew/nightshift-community">github.com/doctor-ew/nightshift-community</a></p>

<div class="tagline">Questions and discussion</div>

<div class="source">Community source repository</div>

<!--
Invite discussion about specifications, independent review, source-bound evidence and provider routing. If asked what to add next, distinguish capability research from the already verified demonstration path. For these talks, keep Codex/Claude, defer Hermes and leave Jev offline. User-facing links resolve to the actual repository; the integrated PR still needs its main merge if #132 remains open.
-->
---
src: ./shared-connect.md
---

---
src: ./shared-appendix.md
---
