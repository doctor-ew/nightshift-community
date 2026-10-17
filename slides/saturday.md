---
theme: default
title: "Trust doesn't rust"
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

<div class="slide-number">ATL DEV CON</div>

# Trust doesn't rust

<div class="hero-sub">Engineering guardrails<br>for AI coding agents</div>
<div class="tagline">Drew Schillinger<br>Enterprise Architect and community builder</div>
<div class="event-details">17 October 2026<br>FCS Innovation Academy, Alpharetta</div>

<div class="source">ATL Dev Con 2026</div>

<!--
The supplied ATL Dev Con speaker poster names this talk “Trust doesn't rust”. The 8 AM to 5 PM poster time is the event window, not the speaking slot. Use the 20-minute core or expand toward 40 minutes. Open with the real distinction between a model finishing and engineering evidence establishing completion. Nightshift makes that distinction inspectable. Source: supplied speaker poster; AGENTS.md; docs/133/IMPLEMENTATION.md.
-->
---

<div class="slide-number">TRUST</div>

# Trust needs current evidence

<div class="two"><section><h3>What was accepted</h3><p>A specification, source state and test evidence.</p><p>A receipt records the accepted attempt.</p></section><section><h3>What changed</h3><p>Changed source can make earlier evidence stale.</p><p>The controller rechecks current bindings.</p></section></div>
<div class="takeaway">Confidence has a scope and a source revision.</div>

<div class="source">scripts/nightshift-pipeline.py; scripts/nightshift-cleanup.py</div>

<!--
Connect the title to engineering: retained success remains useful while its inputs and evidence still match. A prior green check does not approve later source changes. Use the duration formatter rather than asserting that every autonomous agent task is safe. Source: controller input signatures, completed-worktree checkpoint and docs/133/VALIDATION.json.
-->
---
src: ./shared-core.md
---

---
class: closing
---

<div class="slide-number">ATL DEV CON</div>

# Trust doesn't rust

<p class="big">Keep the specification, current source and evidence connected.</p>
<p class="repo-link"><a href="https://github.com/doctor-ew/nightshift-community">github.com/doctor-ew/nightshift-community</a></p>
<div class="tagline">Questions and discussion</div>

<div class="source">Nightshift community</div>

<!--
Close on observable engineering practice. The harness preserves past attempts and validates the current one. Ask the audience where their own AI workflow currently treats a provider result as sufficient evidence. Keep the operational limits from slide 14 visible in discussion.
-->
---
src: ./shared-connect.md
---

---
src: ./shared-appendix.md
---
