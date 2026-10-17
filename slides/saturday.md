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

<div class="slide-number">WHY ROUTE · COST</div>

# Spend for the work being done

<div class="two"><section><h3>Different tasks</h3><p>Source lookup, implementation and adversarial review ask for different capabilities.</p></section><section><h3>Total work cost</h3><p>Compare context, tool support, retries, latency and acceptance—not just one response.</p></section></div>
<div class="takeaway">The cheapest useful route is the one that produces accepted work with less total effort.</div>
<div class="source">routing.json; scripts/nightshift-handoff.py; scripts/nightshift-ticket-budget.py</div>

<!--
Cost is a reason to route, not a measured claim that one named model is always cheaper. A lookup can need strong source tools but less design judgment; implementation and independent review have different responsibilities. A cheap response that creates more repair work can cost more overall. Subscription charges, token-priced estimates, active seconds and elapsed latency are different measures. Local execution also uses hardware and time. In this demo author/reviewer independence, available inventory and subscription policy determined the actual routes; no universal price ranking or measured model-routing savings is claimed. Existing evidence reuse is separately demonstrated by the zero-generation cached repeat.
-->

---

<div class="slide-number">WHY ROUTE · BIAS</div>

# Challenge the author's assumptions

<div class="two"><section><h3>Author</h3><p>Builds from the spec and can become attached to its own interpretation.</p><p>Recorded author: Codex.</p></section><section><h3>Independent reviewer</h3><p>Checks the source, tests and contract instead of accepting the author's summary.</p><p>Recorded reviewer: Claude.</p></section></div>
<div class="takeaway">A second provider adds a different perspective. Shared blind spots can still survive.</div>
<div class="source">routing.json; scripts/nightshift-agent.sh; docs/133/IMPLEMENTATION.md</div>

<!--
Separate author and reviewer provenance reduces direct self-approval; it does not prove statistical independence, remove bias or guarantee defect detection. Models can share training patterns and make the same wrong assumption. Separate role instructions, direct source inspection, adversarial questions and independently executed tests matter alongside provider diversity. Show the actual routes from the retained public rehearsal rather than ranking vendors. The review must challenge the test oracle and requirements, not merely agree that tests are green. Do not claim that two models agreeing is proof.
-->

---

<div class="slide-number">WHY ROUTE · TRUST</div>

# Trust the checks around each worker

<div class="three"><section><h3>Before dispatch</h3><p>Explicit policy, available runtime, scope and retained allowance.</p></section><section><h3>At the boundary</h3><p>Role contract, structured output and locally checked evidence.</p></section><section><h3>Before delivery</h3><p>Review, drift and QA; explicit human decisions where required.</p></section></div>
<div class="takeaway">Switching models changes the worker. It does not relax the gate.</div>
<div class="source">scripts/nightshift-provider-policy.py; contracts/; scripts/nightshift-pipeline.py; AGENTS.md</div>

<!--
Trust means knowing which claims were checked and which authority the worker actually has. A schema-valid response is necessary at a provider boundary but insufficient to establish correct behavior. The controller must validate receipts and input/evidence bindings, and applicable checks must pass. An unavailable local model is not an excuse to silently change billing authority. A confidence score from Jev or any worker cannot approve a production deployment or manufacture manual acceptance. Different provider capabilities and sandbox implementations still need their own verification; runtime-neutral instructions are not a claim that every provider has identical security properties. This is defense in depth, not a formal guarantee of agent containment.
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

<div class="slide-number">NIGHTSHIFT BUILDS NIGHTSHIFT</div>

# We pointed it at itself

<div class="stage-grid"><section><b>1</b><h3>Build</h3><p>A control-room UI for Nightshift.</p></section><section><b>2</b><h3>Challenge</h3><p>Review catches a hidden continuation control.</p></section><section><b>3</b><h3>Repair</h3><p>Restore access. Tests and re-review pass.</p></section></div>

<div class="takeaway">It caught a regression—and exposed its own workflow bug.</div>
<p>Merged after operator approval.<br>The original run stopped at its work allowance.</p>

<div class="source"><a href="https://github.com/doctor-ew/nightshift-community/issues/138">#138 · Real run and evidence ↗</a> &nbsp; <a href="https://github.com/doctor-ew/nightshift-community/issues/139">#139 · Human acceptance sent to code repair ↗</a> &nbsp; <a href="https://github.com/doctor-ew/nightshift-community/pull/140">#140 · Operator-directed merge ↗</a></div>

<!--
This happened while preparing these talks. We asked Nightshift to improve Nightshift's dashboard, using the canonical controller, isolated runtime/worktree, Codex authoring and Claude independent review. Product, Adversarial and Implementation passed. First Review failed because an existing continuation control was hidden inside a closed disclosure. Implementation repaired accessibility and ambiguous receipt labels; independent re-review and Drift passed. QA's automated checks passed, but the QA stage failed on required human visual case C-6. The controller incorrectly routed that human-only finding back to Implementation. The persisted 3,600 active-second allowance exhausted before that worker could do substantive work. The original run did not fabricate acceptance, reset its budget or complete automatic publication. The operator subsequently explicitly instructed merge after seeing the preview and run limitations. PR 140 records operator-directed delivery; the old failed receipts remain unchanged. Issue 139 records the sequencing defect and remains open. A source merge is distinct from a stable release or replacing a private installation; check current release state before claiming either. This is a real partially completed run, separate from the completed duration-formatter rehearsal. Open issue 138 for durable evidence; localhost:8880 is the candidate on the presenter laptop only. Allow about one minute: build, challenge, repair, then the honest stop. Sources: issue138 result comment6201648902; issue139; retained controller receipts/state for138. Do not describe all six stages or final proof as passed. Explain the default 3,600 active-second allowance as a sum of tracked invocation durations, including overlapping parent stages and nested roles: about 51 minutes elapsed accumulated 60 minutes in the ledger. It is not model compute time or billed cost. The 64-reservation ceiling was not exhausted (17 reserved). The operator merge direction is recorded separately from a claim that they personally ran every viewport/keyboard check.
-->

---

<div class="slide-number">DEEP DIVE</div>

# Human checkpoints

<div class="two"><section><h3>Declared operating mode</h3><p>Supervised planning waits for approval.</p><p>Autonomous planning records its plan and continues.</p></section><section><h3>Explicit boundaries</h3><p>Production deployment requires confirmation.</p><p>Permanent removal requires confirmation.</p></section></div>
<div class="takeaway">Passing a test does not grant new authority.</div>

<div class="source">AGENTS.md; commands/nightshift-implement.md</div>

<!--
Optional expansion for a 30–40 minute slot. Distinguish the repository policy from what an LLM says it may do. The supervised and autonomous plan paths are explicit in the implementation command. Production deployment and permanent deletion require operator confirmation. Do not claim prompt text alone enforces a security boundary. Source: AGENTS.md Autonomy and confirmation policy; commands/nightshift-implement.md Step 3.
-->

---

<div class="slide-number">FROM MY FIRST TALK</div>

# From memory to accountable work

<div class="two"><section><h3>In Pursuit of Memory</h3><p>Carry useful context between sessions.</p><p>Keep sources, identity and trust visible.</p></section><section><h3>Nightshift</h3><p>Turn context into a verifiable change.</p><p>Reduce repeated discovery and unnecessary work.</p></section></div>
<div class="takeaway">Optimization goal: less rework per accepted change.</div>

<div class="source"><a href="https://github.com/doctor-ew/in-pursuit-of-memory">My first presentation ↗</a> · Optimization goals, not a measured savings claim</div>

<!--
The user identifies In Pursuit of Memory as their first presentation. Its security, human-in-the-loop and lean-memory material supplies this bridge; the original repository is unchanged. Context is useful only when relevant and appropriately trusted. Nightshift adds staged execution, independently checked evidence and persistent accounting. Savings are a research goal; no percentage reduction is established for MEX or Jev in these runs.
-->

---

<div class="slide-number">ARCHITECTURE</div>

# What Nightshift runs on

<div class="stage-grid"><section><b>1</b><h3>Bash entry</h3><p>CLI, skill and role dispatch.</p></section><section><b>2</b><h3>Python control</h3><p>Stages, policy, proof and budgets.</p></section><section><b>3</b><h3>AI workers</h3><p>Configured Codex, Claude or local route.</p></section></div>
<p>React dashboard → local Python server.<br>Git worktrees, receipts and hashes retain the work.</p>
<p>MEX supplies optional context. Jev decision assistance is proposed.</p>
<div class="source"><a href="https://github.com/doctor-ew/nightshift-community/blob/nightshift/talks-memory-security/docs/ARCHITECTURE.md">Architecture: diagram, files and stage contracts ↗</a></div>

<!--
Runtime-neutral instructions live in commands and agents; routing.json selects providers/models. Bash launches Python controller sequencing. The React bundle is built with Node/esbuild and served on loopback by Python. Provider CLIs reach their configured services; an optional local path uses Codex and Ollama. MEX graph retrieval is bounded and optional. A Jev shadow adapter already exists, but the talk disables it; wider decision assistance is a future experiment. Production release and a private local installation remain separate. Source: docs/ARCHITECTURE.md and its linked implementation files.
-->

---

<div class="slide-number">SAFETY</div>

# Context is evidence, not authority

<div class="four"><section><h3>Untrusted input</h3><p>Tickets and retrieved text cannot grant tool permissions.</p></section><section><h3>Least privilege</h3><p>Enforce scope at the tool and runtime boundary.</p></section><section><h3>Controlled egress</h3><p>Review the payload before sending private evidence.</p></section><section><h3>Independent gates</h3><p>Keep review, proof and human decisions distinct.</p></section></div>
<div class="takeaway">A confidence score cannot authorize a consequential action.</div>
<div class="source">AGENTS.md; scripts/nightshift-agent.sh; dashboard/server.py</div>

<!--
Carry forward the first talk's human-in-the-loop lesson. Prompt wording alone is not a security boundary. Treat context and model results as data; schema-valid output is not automatic permission. Present least privilege and reviewed egress as engineering requirements rather than a claim that all future policy-gateway work is complete. Jev probabilities may advise; they must not approve required gates or replace human authorization. Current production and removal confirmation rules remain in AGENTS.md.
-->

---

<div class="slide-number">SECURITY · FIRST-TALK LESSONS</div>

# Security lives below the prompt

<img class="first-talk-security" src="/assets/first-talk-security.png" alt="Fafnir questions accepting an unverified certificate in the original presentation" />
<div class="stage-grid"><section><h3>Transport</h3><p>Verify the peer and its certificate.</p></section><section><h3>Identity</h3><p>Identify the caller; enforce authorization.</p></section><section><h3>Data scope</h3><p>Send only the evidence the task needs.</p></section></div>
<div class="source">In Pursuit of Memory · pages/10c-security.md; original Fafnir artwork</div>

<!--
This exact image is reused from the user's first presentation. That talk discussed disabled certificate validation, missing per-user identity and shared-password authentication. Those are lessons from that application, not a claim that Nightshift currently uses that application's authentication provider. The Nightshift dashboard is locally bound and validates mutation requests; that does not certify it as a publicly hosted multi-user application. Show the distinction between transport security, caller identity, authorization and model instructions.
-->

---

<div class="slide-number">MEMORY</div>

# Retrieval is one part of memory

<div class="two"><section><h3>Vector retrieval</h3><p>Find candidate context by similarity.</p><p>A relevant match still needs a source.</p></section><section><h3>Memory management</h3><p>Track provenance, revision and freshness.</p><p>Decide what to retain, share and retire.</p></section></div>
<div class="takeaway">Remember the reason—and the evidence it depends on.</div>
<div class="source">Memory design distinction · MEX grounding documentation; first-talk memory material</div>

<!--
Vector search and governed memory solve different parts of the problem. Similarity is a retrieval signal, not proof that a fact remains true or that the caller may see it. MEX's upstream design uses repository knowledge plus a code graph; do not describe it simply as a vector database. Keep private data scope and stale-context handling visible. This is an architectural explanation, not a benchmark result.
-->

---

<div class="slide-number">MEX</div>

# MEX: carry the team's context

<div class="two"><section><h3>Repository memory</h3><p>Architecture, decisions and handoffs through Git.</p><p>Code-linked grounding and a local graph.</p></section><section><h3>My contribution</h3><p>I contributed the C# code-graph extractor.</p><p>A concrete open-source entry point for .NET engineers.</p></section></div>
<p>Nightshift can retrieve bounded source context when the graph is available.</p>
<div class="source"><a href="https://github.com/mex-memory/mex">MEX ↗</a> · <a href="https://github.com/mex-memory/mex/commit/7bc7e7f1f692a4d9053792dd61129e47bfb89049">My C# contribution ↗</a> · scripts/nightshift-handoff.py</div>

<!--
Contribution attribution is verified by upstream commit7bc7e7f1, author Drew Schillinger. Current upstream documents partial C# coverage; this is not complete .NET semantic analysis. Local Nightshift retrieval rejects missing, stale or partial graph evidence. No measured MEX token saving is claimed here.
-->

---

<div class="slide-number">JEV · COMING NEXT</div>

# Ask a smaller decision

<div class="two"><section><h3>Candidate uses</h3><p>Classify a narrow claim.</p><p>Suggest a route or relevant context.</p><p>Return typed choices and confidence.</p></section><section><h3>Nightshift boundary</h3><p>Optional shadow adapter exists.</p><p>Disabled in this demonstration.</p><p>Required independent review stays.</p></section></div>
<div class="takeaway">First measure decisions. Then decide what to delegate.</div>
<div class="source"><a href="https://www.jevai.org/docs">Jev community decision workflows ↗</a> · scripts/nightshift-jev-evaluation.py</div>

<!--
The supplied Jev site is a community hub, distinct from TypeSafe AI's core model service. Its docs describe typed decision workflows and treat probabilities as signals, not authorization. Wider Nightshift use is proposed. The current local evaluation adapter requires explicit evidence, reports zero avoided Claude calls, and does not replace a required reviewer. No external payload is sent for this presentation update; no Jev accuracy, latency or savings benchmark is established. Evaluate on labeled public cases, record false positives/negatives and abstention, and retain required independent gates.
-->

---

<div class="slide-number">COST AND OPTIMIZATION</div>

# Measure cost per accepted change

<div class="four"><section><h3>Context</h3><p>Retrieve and hand off the relevant evidence.</p></section><section><h3>Routing</h3><p>Match the worker to the actual task.</p></section><section><h3>Reuse</h3><p>Reuse accepted work while bindings match.</p></section><section><h3>Quality</h3><p>Count rework and missed defects too.</p></section></div>
<p>Track tokens, calls, elapsed time, retries and acceptance.<br>Reported estimates and actual billed cost are different measures.</p>
<div class="source">scripts/nightshift-handoff.py; scripts/nightshift-ticket-budget.py; docs/talks/TESTING.md</div>

<!--
The completed formatter repeat demonstrated zero additional generation calls with unchanged receipts/reservations; it did not measure general cost savings from MEX or Jev. Evaluate alternatives against the same accepted outcome and include failed attempts, retries, decision overhead and quality. Active-time accounting sums overlapping invocations; it is not elapsed wall time or billed cost. Provider subscription use and token-priced estimates do not establish actual incremental charges. The goal is useful, verified work with less unnecessary processing.
-->

---

<div class="slide-number">CONTROL ROOM · ACTUAL LOCAL CAPTURE</div>

# The current control room

<img class="walkthrough-shot" src="/assets/control-room-actual.png" alt="Actual task 138 control room with six selectable stages and retained attempt evidence" />
<p class="walkthrough-caption">Select a stage → inspect its worker, evidence and history. This retained run needs revalidation.</p>
<div class="source">Actual local dashboard · task 138 · 17 October 2026 · dashboard/src/app.jsx</div>

<!--
This is the current local control room, not a mockup. The task is the dashboard change itself. The recorded state is stale because evidence changed; it is not an active successful run. Point out the stage selector, provider/model and retained attempts. Switching stages is inspection and does not dispatch work. The older completed formatter at port 8878 uses its pinned runtime and therefore has an older front end. This screenshot comes from port 8880. Source: dashboard/src/app.jsx; docs/138/OPERATOR-DELIVERY.md.
-->

---

<div class="slide-number">STAGE EVIDENCE · ACTUAL LOCAL CAPTURE</div>

# Review keeps the failed attempt

<img class="walkthrough-shot" src="/assets/stage-review-actual.png" alt="Actual Review stage showing its recorded route, receipts and retained attempts" />
<p class="walkthrough-caption">The first review found a hidden control. The repair passed the next review; earlier evidence remains.</p>
<div class="source">Actual task 138 Review panel; docs/138/IMPLEMENTATION.md; docs/138/REVIEW.md</div>

<!--
The first integrated browser check found a hidden continuation control below long evidence; the primary control was moved above it. Review then passed. This is one stage's outcome, not a claim that the entire factory run completed. The panel displays recorded receipt paths; the controller and independent checks validate their contents. Open the Review tab live if time permits; no Resume click is needed.
-->

---

<div class="slide-number">HUMAN IN THE LOOP · ILLUSTRATIVE QUESTION</div>

# Answer the missing requirement

<img class="walkthrough-shot" src="/assets/hitl-question-illustrative.png" alt="Real dashboard question component with an illustrative public formatter type-boundary question" />
<p class="walkthrough-caption">Real UI with illustrative data. No answer submitted and no run started.</p>
<div class="source">dashboard/src/ticket-live.jsx · TicketDecision; scripts/nightshift-console-decisions.py</div>

<!--
The question and options are staged public examples rendered by the real unmodified UI using a browser-only substituted GET response. They are not historical operator testimony. Explain: the original requirement says seconds, so the agent should not silently invent float rounding. The operator can choose integers or fractional seconds, or write an answer. The saved answer binds to the exact question hash and task/settings identity. It does not manufacture a passing review or test result. No form was submitted during screenshot capture.
-->

---

<div class="slide-number">HUMAN IN THE LOOP · ILLUSTRATIVE SPEC</div>

# Approve a specific spec version

<img class="walkthrough-shot" src="/assets/hitl-spec-illustrative.png" alt="Real dashboard spec approval component displaying an illustrative formatter contract and Approve and continue button" />
<p class="walkthrough-caption">Read the contract before continuing. Changed inputs require fresh approval.</p>
<div class="source">Illustrative data in actual UI; dashboard/src/app.jsx; scripts/nightshift-console-actions.py</div>

<!--
This uses the actual approval component with a public illustrative formatter spec. It is not evidence that task 138 received this spec approval, nor a claim that every pipeline stage uses this workshop approval path. The console computes an identity over the record and review content, and checks that identity before acting. Approval is scoped to the displayed version. Spec approval, answering a question, manual visual acceptance and production authorization are separate decisions. No button was clicked.
-->

---

<div class="slide-number">WORK ALLOWANCE · ACTUAL LOCAL CAPTURE</div>

# A stopped worker is not a verdict

<img class="walkthrough-shot allowance-shot" src="/assets/allowance-actual.png" alt="Actual task 138 allowance showing budget exhausted, zero active seconds remaining and 17 of 64 launches reserved" />
<p class="walkthrough-caption">Active time sums tracked invocations, including overlap. It is neither wall time nor a token bill.</p>
<div class="source">Actual task 138 allowance; scripts/nightshift-ticket-budget.py; docs/138/OPERATOR-DELIVERY.md</div>

<!--
The actual card records 3,601 aggregate active seconds and 17/64 launches. Its active allowance is exhausted even though launch capacity remains. Overlapping parent stage and nested role durations can both contribute. Model completion has no arbitrary conversational deadline; an explicit retained operator work allowance is a separate bound. A time stop means work ceased; it does not prove the candidate is bad or good. Continuation preserves prior evidence and limits. Do not click the continuation button while presenting unless intentionally authorizing more work. The operator merge did not rewrite failed QA or manual case C-6 as passed.
-->

---

<div class="slide-number">SKILLS · THE ACTUAL ADAPTER</div>

# Inside the Nightshift skill

<div class="terminal detail-code"><div class="terminal-label">skills/nightshift/SKILL.md · EXCERPT</div><pre>## Invocation
`$nightshift &lt;ticket-ref&gt;`
Advanced form: `$nightshift &lt;stage&gt; &lt;arguments&gt;`
Advisory commands: `help`, `explain`, `architect`,
`dev`, `pm`, `ux-designer`, `architecture`, `ux`, `bmad`.</pre></div>
<p>One adapter loads shared instructions. Roles and provider selection live separately.</p>
<div class="source">skills/nightshift/SKILL.md; commands/; agents/; routing.json</div>

<!--
This excerpt comes from the repository's actual Codex adapter; angle-bracket arguments are placeholders. Open the file to show that it deliberately avoids a second drifting prompt set. A skill supplies instructions and entry conventions; scripts and the controller execute/check the workflow. The same core also has a Claude adapter. Advisory architect/dev/PM/UX commands help plan or explain and do not count as passed engineering gates. A full ticket invocation is distinct from requesting one advisory role.
-->

---

<div class="slide-number">SKILLS · ROLE DISPATCH</div>

# Follow one Product-stage handoff

<div class="terminal detail-code"><div class="terminal-label">REPOSITORY FILES IN THE DISPATCH PATH</div><pre>skills/nightshift/SKILL.md
  → commands/nightshift-product.md
  → agents/nightshift-code-fact-extractor.md
  → agents/nightshift-spec-writer.md
scripts/nightshift-agent.sh + routing.json
  → provider invocation + validated role output</pre></div>
<p>The extractor grounds identifiers. The writer cites sources and records unknowns.</p>
<div class="source">commands/nightshift-product.md; agents/nightshift-spec-writer.md; scripts/nightshift-agent.sh</div>

<!--
This is a responsibility map, not an exact shell call trace: Product orchestrates multiple helpers. The stage's hard rule is upstream ticket authority; Beads is a local mirror. The extractor checks names against source, then the writer produces the spec. The role prompt remains runtime-neutral. Routing and author provenance select the worker; normalized JSON output is checked against the role contract. The controller validates stage evidence before advancement. Never equate the model returning JSON with the stage having passed.
-->

---

<div class="slide-number">HARNESS · ACTUAL TEST EVIDENCE</div>

# Follow the formatter's proof trail

<div class="terminal detail-code"><div class="terminal-label">RETAINED PUBLIC TASK ARTIFACTS</div><pre>SPEC.md + behavior-scenarios.json
  → implement-2-red.log   (expected failure)
  → proof-red.json       (development proof)
  → duration.py + tests/test_duration.py
  → proof-final.json     (final proof)</pre></div>
<p>Three tests cover 26 inputs. Later review and QA inspect the resulting evidence.</p>
<div class="source">Public formatter worktree docs/spec-014c777fd4684e19/; docs/133/IMPLEMENTATION.md</div>

<!--
These are actual artifact names in the retained public task. The earlier Implementation attempt ran the RED phase; the accepted receipt later validated retained evidence without repeating implementation. The original failure is preserved. The tests cover seven example/boundary values, three negative integers and sixteen excluded types. Explain that a proof artifact is a structured claim checked against actual execution and bindings. Missing or changed source, tests or receipts invalidate reuse. Use python3 scripts/nightshift-talk-check.py for a guarded repeat; this rechecks existing work and blocks new model generation.
-->

---

<div class="slide-number">HUMAN IN THE LOOP · CONTINUATION CONTRACT</div>

# The answer does not pass the gate

<div class="flow"><span>Exact question</span><i>→</i><span>Saved answer</span><i>→</i><span>Admission check</span><i>→</i><span>Resume or block</span></div>
<div class="two"><section><h3>Retain the decision</h3><p>Task, question and settings remain bound. Repeated questions can reuse the answer.</p></section><section><h3>Retain the uncertainty</h3><p>Changed evidence needs revalidation. Tests and reviews still decide their own outcomes.</p></section></div>
<div class="source">scripts/nightshift-console-decisions.py; scripts/nightshift-console-actions.py</div>

<!--
The pending question has a sha256 identity. Submission carries task, settings hash, question hash, choice and optional free text. The helper rejects stale bindings. Stable decision keys or normalized identical questions can reuse an existing answer; reopening requires the prior answered hash and a reason. Continuation can be resume, repair or none. A saved answer can remain recorded even if a continuation is blocked; the UI exposes retry for that continuation. This is a durable control-plane decision, not another model message and not a manual-acceptance attestation.
-->

---

<div class="slide-number">MEX · THE IMPLEMENTED CONTEXT BOUNDARY</div>

# MEX retrieval inside a handoff

<div class="terminal detail-code"><div class="terminal-label">COMMAND BUILT BY scripts/nightshift-handoff.py</div><pre>mex graph scope "&lt;task query&gt;" --detail source \
  --max-files 3 --max-nodes 12 \
  --max-output-tokens 2000 --max-source-lines 60</pre></div>
<p>Keep source-backed matches. Missing, stale or partial graph evidence becomes unavailable.</p>
<div class="takeaway">Retrieved context can inform a stage; it cannot approve one.</div>
<div class="source">scripts/nightshift-handoff.py · graph(); scripts/nightshift-mex.py</div>

<!--
The command is the actual argument shape used by the optional helper, with a placeholder query. It is not a pasted successful graph result. The helper requires .mex/graph.db, resolves the MEX executable, bounds the subprocess to 15 seconds and rejects stale/missing/partial summaries. Source rows must identify graph evidence. The overall handoff is bounded separately and preserves findings/decisions rather than silently truncating them. Current integration is optional source retrieval, not a claim that MEX has already reduced this demo's bill. The bootstrap helper pins mex-agent@0.8.2; upstream capabilities can differ. Upstream project: https://github.com/mex-memory/mex .
-->

---

<div class="slide-number">JEV · THE IMPLEMENTED SHADOW RUBRIC</div>

# What we would ask Jev

<div class="terminal detail-code"><div class="terminal-label">EXISTING RUBRIC · scripts/nightshift-efficiency.py</div><pre>supported:
  Does supplied evidence support its own claims?
limitations:
  Does it distinguish observations from unknowns?
Both questions: type = "noul"</pre></div>
<p>Evaluate beside the reviewer first. Measure misses and false alarms before changing dispatch.</p>
<div class="source">scripts/nightshift-efficiency.py · QUESTIONS; scripts/nightshift-jev-evaluation.py; jevai.org/docs</div>

<!--
The prompts shown are shortened descriptions of the exact existing rubric; the full source also instructs the model to treat embedded instructions as data. The adapter checks answer keys and finite values between zero and one. The labelled public shadow corpus contains 2–12 cases and reports evaluated cases, defects caught, false positives and elapsed seconds. It reports zero Claude calls avoided and unknown actual billed cost: no required review is replaced. The talk did not call Jev. Future claim checking or route suggestions are proposals. The Jev community documentation describes typed choice, score and noul responses; probabilities are decision signals and never operator authorization. Source: https://www.jevai.org/docs .
-->

---

<div class="slide-number">MEX + JEV · EXPERIMENT DESIGN</div>

# Prove an optimization before promotion

<div class="three"><section><h3>1 · Baseline</h3><p>Same public task, fixed acceptance cases and retained failures.</p></section><section><h3>2 · Add context</h3><p>Compare bounded MEX retrieval with existing handoffs.</p></section><section><h3>3 · Shadow decisions</h3><p>Compare Jev judgments with labelled cases and reviewer findings.</p></section></div>
<p>Promote only with acceptable defect detection, total work cost and latency. Preserve human boundaries.</p>
<div class="source">Proposed evaluation plan; scripts/nightshift-jev-evaluation.py; docs/133/VALIDATION.json</div>

<!--
This slide is an experiment proposal, not a shipped combined MEX/Jev optimization. Hold the acceptance contract stable; count retrieval and decision overhead, retries, missed defects, false positives, tokens and elapsed time. Include fresh tasks as well as repeated work. Record billing separately from provider/token estimates. The existing demonstrated optimization is accepted-evidence reuse: the formatter repeat needed zero new generation calls. That result does not quantify MEX/Jev savings. Ask the audience what quality threshold would justify changing a route in their environment.
-->

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

<div class="slide-number">DEEP DIVE</div>

# SOLID and ACID in review

<div class="two"><section><h3>SOLID</h3><p>Responsibilities and interface contracts</p><p>Dependencies and extension points</p></section><section><h3>ACID</h3><p>Validation and consistent state</p><p>Isolation and recovery for state changes</p></section></div>
<div class="takeaway">These are review lenses. Findings still need evidence.</div>

<div class="source">commands/nightshift-review.md</div>

<!--
Optional expansion for a 30–40 minute slot. The canonical review command includes SOLID and ACID, among other lenses. ACID review applies to state-mutating code. This is a review discipline, not a claim that every file or distributed workflow is transactionally ACID. Findings require a lens, severity, confidence, file/line and description. Source: commands/nightshift-review.md SOLID, ACID and finding format.
-->
