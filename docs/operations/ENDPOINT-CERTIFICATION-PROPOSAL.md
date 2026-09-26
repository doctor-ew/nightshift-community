# Endpoint certification and activation proposal

## Authorization status

This proposal does not authorize execution. No live provider, real ticket restart,
live allowance, installed-runtime replacement, merge or deployment is included in
the implementation run. Issue #2 remains open. Promotion still follows
`docs/PROMOTION.md`; the current stacked topic branches are not an integrated
release revision.

## Candidate selection

Pin the final reviewed delivery candidate by full commit ID and retain its exact
source, test reports, dependency heads and GitHub check results. Retest any changed
candidate. A topic-branch test cannot certify an eventual integration commit. Before
live authorization, resolve the exact integration revision and inspect all required
checks, rather than substituting the latest previous report.

## Endpoint matrix

| Profile | Required evidence | Additional authorization |
| --- | --- | --- |
| Local operations through Review | Fresh reference, independent Groom/Review, typed tests, replay, bounded repair and exhaustion/adoption | Exact subscription route, operation binding and bounded grant |
| Human acceptance | Current manual-case observations and evidence, stale evidence rejection, browser/CLI parity | Operator attestation for exact cases |
| Published branch | Above plus scoped commit, exact local/remote head, preserved unrelated work and crash reconciliation | Explicit remote, branch and intended files |
| Open PR | Above plus owned PR identity and duplicate reconciliation | Explicit repository/base and PR endpoint |
| Integration CI | Above plus trusted check application IDs, exact merge candidate/parents, bounded repair and fresh acceptance | CI endpoint and any existing bounded repair grant |
| Integrated change | Above plus branch policy and host-confirmed merge | Separate merge authorization; excluded from this run |
| Deployment (#74) | Environment identity, health, promotion and rollback evidence | Separate optional profile; excluded |
| Shared service (#75) | Authenticated principals, role isolation and service-specific audit evidence | Separate optional profile; excluded |

Package runs additionally require parent integration tests and reconciled child /
parent accounting. Passing children alone cannot certify the parent endpoint.
Optional Jev evaluates a labeled bounded handoff corpus separately; disabled Jev
must remain usable. Synthetic control-flow tests do not establish semantic accuracy
or a savings claim.

## Proposed local live shakedown

1. Select the exact integrated Community commit after separate integration approval.
   Use a fresh clone and new isolated installer targets. The supported installer
   arguments are `--target`, `--codex-target`, `--nightshift-target` and
   `--bin-target`; pass all four explicitly. Use `--auth subscription` and the
   selected runtime. Run `install.sh --check` against those same targets. Preserve
   the existing operator installation and retained state.
2. Prepare a disposable repository with the #2 public practice specification: a
   Python slugify function and CLI, lowercase ASCII letters, whitespace runs to a
   hyphen, clear rejection of unsupported punctuation, and unittest coverage of
   empty input, repeated whitespace, uppercase input and invalid punctuation.
   Exercise both `spec:` and bare Markdown references, including spaces. This
   local practice run has no push or PR endpoint.
3. Resolve the configured author and independent reviewer provider/model and
   subscription authentication. Record route identities without copying credentials
   or private configuration. Reject missing independent review and paid-API
   fallback. Prepare a proposal containing the exact task/source digest, plan
   binding, scope, per-operation limits, aggregate call/seconds/wall limits,
   cancellation identity and requested recipe. Do not grant it yet.
4. Request a single explicit authorization for that concrete bounded live proposal.
   Once authorized, run the actual isolated launcher and loopback browser. Retain
   Sources, adversarial findings, implementation diff, typed results, manual cases,
   independent Review and the terminal receipt. Demonstrate browser evidence and
   refresh rather than relying on HTTP success alone.
5. Check active-run update deferral with the configured Community source/channel.
   Re-run applicable offline checks. Report failures, skips and missing evidence
   as blocking. An independent reviewer examines the exact retained receipt before
   any promotion proposal.

## Proposed bounded local profile

The reviewable input is `CERTIFICATION-PRACTICE.md`; its digest and proposed limits
are in `CERTIFICATION-PROPOSAL.json`. This prepared procedure is not an executable
activation approval packet until its exact candidate, destination inventory and
source/authorization bindings are populated. Null fields explicitly remain pending.

The proposed first live endpoint is `review_pending_manual_acceptance`, with no
publication target and Jev disabled. Proposed aggregate ceilings are 12 provider
calls, 1,200 execution seconds and 1,800 wall seconds. Each AI operation has at most
four calls and 240 execution seconds within that same aggregate deadline; automatic
repair still has the existing three-attempt limit. Deterministic checks have a
120-second ceiling. These are proposed limits, not a created allowance.

The public `routing.json` currently selects Codex `gpt-5.4` for ordinary author
roles and its cross-provider alternates include Claude `sonnet`. This is a source
configuration observation, not verified live availability. The proposed profile
retains subscription authentication and mandatory independent-provider review. If
those routes are unavailable, stop and prepare a newly reviewed configurable route;
do not infer permission for a paid API or substitute an unreviewed model.

The disposable source scope is the slugify implementation, CLI and unittest tests.
The required manual case invokes the CLI with uppercase text and repeated spaces,
records the exact command/output and checks rejection of unsupported punctuation.
A fresh assessment must bind the actual prepared files and runtime immediately
before authorization. A grant from synthetic testing cannot be reused for this run.

## Separate remote delivery proposal

A later branch/PR/CI live certification uses another disposable public repository
and explicit host permissions. Pin the push URL, repository, base/head revisions,
intended file hashes, required trusted check IDs and endpoint. Demonstrate remote
reconciliation, rejected/stale targets and parent CI failures without merging.
A local #2 shakedown does not authorize this remote profile. Never enable deployment
or service identity merely to certify local branch/PR delivery.

## Receipt and activation

Each receipt records full runtime revision, installation identity, OS/interpreter /
browser versions, input hashes, provider/model/auth mode, request byte sizes,
actual calls, cache/operation reuse, escalation, wall and execution time, unknown
reservations, token/billing fields or explicit unknowns, independent verdict and
limitations. Keep implementation, integrated synthetic acceptance, temporary
installation, live certification and activation as separate fields. Raw logs stay
private; public evidence must omit private paths, credentials and ticket contents.

Activation is a separate proposal after certification. The first proposed target
is a separate Community profile with its own runtime, adapters and bin directory;
the existing global launcher must not be redirected. Invoke that profile by its
explicit launcher path. Retiring the candidate profile means stopping its owned
processes and ceasing to invoke that path, while preserving its evidence; it does
not require uninstalling or deleting the existing runtime. The activation proposal
must pin the exact candidate, destination inventory, preserved prior runtime,
retained state locations, rollback procedure and post-install identity checks. No real-ticket continuation is
implicit. A changed activated revision requires fresh affected certification.
