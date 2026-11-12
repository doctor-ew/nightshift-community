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
