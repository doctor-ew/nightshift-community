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

<div class="slide-number">OVERVIEW</div>

# The harness keeps the workflow

<div class="four"><section><h3>Entry point</h3><p>A skill or CLI starts the work.</p></section><section><h3>Canonical instructions</h3><p>Stages and roles define the work.</p></section><section><h3>Routing</h3><p>Configuration selects the provider.</p></section><section><h3>Controller</h3><p>Evidence determines the next stage.</p></section></div>

<div class="source">AGENTS.md; skills/nightshift/SKILL.md; routing.json; scripts/nightshift-pipeline.py</div>

<!--
Explain these as separate responsibilities. Codex skills and Claude commands adapt the same core. The provider is not the canonical workflow implementation. The front end observes and invokes the shared control plane. Source: AGENTS.md; dashboard/src/app.jsx; scripts/nightshift-pipeline.py.
-->

---

<div class="slide-number">SKILLS</div>

# The skill is the entry point

<div class="terminal"><div class="terminal-label">CODEX SKILL</div><pre>$nightshift &lt;ticket-ref&gt;</pre></div>

<p>The adapter loads the canonical stage instructions.</p>
<p>A ticket starts the engineering pipeline without separate calls for each stage.</p>

<div class="source">skills/nightshift/SKILL.md</div>

<!--
Open skills/nightshift/SKILL.md in the editor. Show Invocation and the statement that the skill reuses canonical instructions instead of keeping a second set of prompts. The placeholder is a ticket reference. The pinned terminal wrapper in the runbook is what we use for this demonstration; do not switch to an unrelated global installation during the talk. Source: skills/nightshift/SKILL.md; docs/133/DEMO.md.
-->

---

<div class="slide-number">SKILLS</div>

# The instructions stay in the repository

<div class="artifact"><p><code>commands/</code> &nbsp; Canonical stage instructions</p><p><code>agents/</code> &nbsp; Reusable role instructions</p><p><code>scripts/</code> &nbsp; Execution and validation</p><p><code>routing.json</code> &nbsp; Provider and model selection</p></div>

<div class="source">AGENTS.md; commands/nightshift-product.md; agents/nightshift-spec-writer.md</div>

<!--
Show commands/nightshift-product.md beside agents/nightshift-spec-writer.md. Distinguish stage orchestration from a role's focused instructions. Routing belongs in routing.json rather than static provider-specific model keys in role files. Source: AGENTS.md Project conventions.
-->

---

<div class="slide-number">HARNESS</div>

# Six stages retain their evidence

<div class="stage-grid"><section><b>1</b><h3>Product</h3><p>Specification and scope</p></section><section><b>2</b><h3>Adversarial</h3><p>Independent challenge</p></section><section><b>3</b><h3>Implementation</h3><p>Tests and source changes</p></section><section><b>4</b><h3>Review</h3><p>Independent code review</p></section><section><b>5</b><h3>Drift</h3><p>Specification alignment</p></section><section><b>6</b><h3>QA</h3><p>Final verification</p></section></div>

<div class="source">commands/nightshift-{product,adversarial,implement,review,drift,qa}.md</div>

<!--
Walk through the stage order once. Each stage leaves an attempt-specific receipt. The controller validates that receipt and the required evidence before advancing. Deployment is a separate operation and is outside this example. Sources: the six canonical stage files; scripts/nightshift-pipeline.py.
-->

---

<div class="slide-number">HARNESS</div>

# A small task makes proof visible

<div class="two"><div class="terminal"><div class="terminal-label">PUBLIC DURATION FORMATTER</div><pre>format_seconds(0)    == "0:00"
format_seconds(125)  == "2:05"
format_seconds(3600) == "60:00"</pre></div><section><h3>Acceptance cases</h3><p>Nonnegative integers format correctly.</p><p>Negative integers raise an error.</p><p>Booleans and other types raise an error.</p></section></div>

<div class="source">Public rehearsal: duration.py; tests/test_duration.py; docs/133/IMPLEMENTATION.md</div>

<!--
This is the real public acceptance fixture. It uses Python's standard library and unittest. Seven example/boundary inputs, three negative integers and sixteen excluded types make 26 inputs across three tests. The implementation and test files live in the registered public worktree named in docs/talks/TESTING.md. Do not imply that this simple task establishes reliability for arbitrary applications.
-->

---

<div class="slide-number">ROUTING</div>

# Routing selects the worker

<div class="two"><section><h3>Author path</h3><p>Codex</p><p><code>gpt-6.1-sol</code></p><p>Product and Implementation</p></section><section><h3>Independent review path</h3><p>Claude</p><p><code>sonnet</code></p><p>Adversarial, Review, Drift and QA</p></section></div>

<div class="takeaway">These are the recorded routes for this acceptance run.</div>

<div class="source">routing.json; accepted controller receipts for issue 133</div>

<!--
Open routing.json and then the dashboard's Controller routing and receipts panel. Model/provider choices are explicit configuration, while actual receipts show what ran. Do not present this pair as a universal model ranking. The talk used subscription authentication, gear 1 and no automatic API billing fallback. Source: docs/133/DEMO.md; retained stage attempt routes.
-->

---

<div class="slide-number">ROUTING</div>

# Admission happens before dispatch

<div class="four"><section><h3>Provider capability</h3><p>Required runtime and tools are available.</p></section><section><h3>Local inventory</h3><p>The configured local model exists before extraction starts.</p></section><section><h3>Retained allowance</h3><p>Existing call and active-time limits still apply.</p></section><section><h3>Bounded context</h3><p>Stage handoffs carry relevant files and findings.</p></section></div>

<div class="source">scripts/nightshift-capability.sh; scripts/nightshift-ticket-budget.py; scripts/nightshift-handoff.py</div>

<!--
The acceptance run chose gear 1 explicitly after a failed automatic local extraction. The earlier failure and its charged calls remain in the history. New wall-clock limits are opt-in, while active-time and call ceilings remain enforced. Hermes is deferred and Jev is offline for this talk. Sources: docs/133/IMPLEMENTATION.md; docs/133/VALIDATION.json.
-->

---

<div class="slide-number">DEMONSTRATION</div>

# The front end shows the evidence

<img class="evidence-header" src="/assets/demo-header.png" alt="Actual public controller ticket marked Complete" />
<img class="evidence-stages" src="/assets/demo-stages.png" alt="Actual public ticket with all six recorded stages passed" />

<p>Routes, receipts, artifacts and retained attempts remain inspectable.</p>

<div class="source">Actual dashboard capture of the verified public rehearsal</div>

<!--
Switch to http://127.0.0.1:8878. Show the completed ticket and the six passing stages. Open Controller routing and receipts, then point to the current passing receipts and earlier failed attempts. The dashboard labels historical failures separately from the completed run. Cost figures are estimates when available; actual billed charges remain unknown. Source: dashboard/src/app.jsx; docs/133/DEMO.md.
-->

---

<div class="slide-number">DEMONSTRATION</div>

# Watch Nightshift work

<div class="terminal"><div class="terminal-label">PRESENTER TERMINAL · FROM THE COMMUNITY CHECKOUT</div><pre>python3 scripts/nightshift-talk-check.py</pre></div>

<p>Recheck six stage receipts, real tests and both proof gates.</p>
<p>Repeat the retained task with zero new generation calls.</p>
<p><a href="http://127.0.0.1:8878" target="_blank">Open the local dashboard ↗</a> · <a href="https://github.com/doctor-ew/nightshift-community/blob/nightshift/talks-135/docs/talks/TESTING.md" target="_blank">Demo setup and commands ↗</a></p>

<div class="source">Presenter laptop: retained fixture and subscription login required. Cached repeat, not a fresh agent run.</div>

<!--
Allow roughly four minutes if the event schedule permits. Keep editor tabs, terminal and dashboard open before presenting. Use the exact pinned wrapper command from the runbook. This repeat demonstrates accepted evidence reuse, not a new author/reviewer run. If the live surface is unavailable, use the actual completed-dashboard recording or offline captured front end in .nightshift/133-fallback/. Do not improvise a global runtime update on stage.
-->

---

<div class="slide-number">DEMONSTRATION</div>

# RED and GREEN remain inspectable

<div class="two"><section><h3>Before implementation</h3><p>Retained RED evidence records expected test failures.</p><p>Frozen cases define the required behavior.</p></section><section><h3>After implementation</h3><p>The real tests pass.</p><p>Development and final proof gates both pass.</p></section></div>

<div class="takeaway">The rejected receipt stays in history.</div>

<div class="source">commands/nightshift-implement.md; docs/133/IMPLEMENTATION.md</div>

<!--
Show the expected RED exit 1 as retained evidence and successful checks as assertions with exit 0. An expected failure is useful TDD evidence, but cannot appear as a failed required check inside a passing stage receipt. The corrected attempt validated hashes and existing tests/proof rather than rerunning RED against GREEN source. Source: retained implement-2 and implement-3 receipts; docs/133/IMPLEMENTATION.md.
-->

---

<div class="slide-number">EVIDENCE</div>

# Zero generation calls on repeat

<div class="counts"><div><b>6</b><span>accepted stages</span></div><div><b>0</b><span>additional generation calls</span></div><div><b>26</b><span>unchanged call reservations</span></div></div>

<p>Receipt hashes and attempt history stayed unchanged.</p>
<p>Current bindings allow the controller to reuse accepted work.</p>

<div class="source">docs/133/VALIDATION.json; retained repeat-validation.json</div>

<!--
The 26 reservations include the acceptance's retained earlier attempts. They are not 26 calls made by this repeat. This is a measured cached repeat, not a claimed percentage saving across arbitrary tasks. Altered source or evidence must be reconciled rather than silently reused. Source: scripts/nightshift-cleanup.py; nine actual-worktree regressions in tests/test-cleanup-controller-resume.py.
-->

---

<div class="slide-number">EVIDENCE</div>

# Verification has a defined scope

<div class="two"><section><h3>Observed</h3><p>One public task passed all six stages.</p><p>Both proof gates and repeat reuse passed.</p><p>Ten CI shards and dashboard checks passed.</p></section><section><h3>Still outside this evidence</h3><p>Reliability across arbitrary projects</p><p>Actual provider billed charges</p><p>Hermes or Jev accuracy and savings</p></section></div>

<div class="source">docs/133/VALIDATION.json; GitHub Actions run 38600812302</div>

<!--
Keep the scope honest and brief. The run is real, the independent reviewer calls are real and earlier failures remain visible. Synthetic controller regressions and browser checks add boundary coverage; they do not replace the live acceptance. Published implementation CI tested revision be272d9, followed by documentation-only evidence updates. Source: docs/133/IMPLEMENTATION.md.
-->

---

<div class="slide-number">EVIDENCE</div>

# Rehearsal and fallback

<div class="two"><section><h3>Before presenting</h3><p>Run the pinned checker.</p><p>Open the dashboard and editor tabs.</p><p>Verify the recorded candidate.</p></section><section><h3>Offline options</h3><p>Actual dashboard recording</p><p>Captured front end with no network</p><p>Retained public project archive</p></section></div>

<div class="source">docs/talks/TESTING.md; docs/133/DEMO.md</div>

<!--
The local assets live under .nightshift/133-fallback/: completed-demo.webm, recorded-dashboard.html and public-project-and-worktree.tar.gz. The offline HTML contains no scripts and makes no network requests. Archive restoration preserves original absolute-path bindings and must not overwrite a newer project. These are local-only assets, not something every audience member receives through the public repository.
-->

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

<div class="slide-number">APPENDIX</div>

# Testing the retained demo

<div class="terminal"><div class="terminal-label">FROM THE COMMUNITY CHECKOUT</div><pre>python3 scripts/nightshift-talk-check.py</pre></div>

<p>The checker validates identity, receipts, proof and real tests.</p>
<p>The repeat check refuses new provider generation.</p>

<div class="source">scripts/nightshift-talk-check.py; docs/talks/TESTING.md</div>

<!--
Use the checker only after following the local setup assumptions in docs/talks/TESTING.md. It is specifically a check of the retained public acceptance fixture. It does not certify an arbitrary default installation or a fresh provider-backed task. If the fixture is missing or stale, report that condition rather than forging new receipts or resetting its budget.
-->

---

<div class="slide-number">APPENDIX</div>

# Merge state and the PR stack

<div class="two"><section><h3>Merged fix</h3><p>PR #134 merged into the integration branch behind PR #132.</p></section><section><h3>Main branch</h3><p>PR #132 remained open against main at the audit.</p></section></div>

<p>The other open PRs need an ancestry and diff audit.</p>

<div class="source">docs/talks/open-pr-audit.md; observed GitHub state on 14 October 2026</div>

<!--
This appendix is presenter context and can be omitted from the talk. At the audit, 32 other open PR heads were already contained in main and 17 diverged. Avoid suggesting that all 50 open PRs represent missing features or that they can all be merged. Recheck status immediately before the talk if using this appendix.
-->
