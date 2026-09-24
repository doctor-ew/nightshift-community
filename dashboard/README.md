# Local operations dashboard

`bash scripts/nightshift-dashboard.sh --serve --project /path/to/repository` prints
its URL and serves at `http://127.0.0.1:8765`. `--port` selects another port.
`--static` (also the script default) preserves standalone HTML stdout output;
`--json` exposes the same bounded collector for local integrations.

The bundled React page refreshes every three seconds and presents recorded states,
filters, summary cards and a maximum of 24 cards per page. Run overview retains
batch and gate claims independently, including concurrent and conflicting states.
Counts refer to source observations, not unique live agents. File modification time
only sorts the display; it is not precedence or a heartbeat, and an in-progress
receipt does not prove an agent is alive. History adds artifacts and ownership.
Failed role output receipts and explicit tracker block receipts appear as gate
evidence and on their ticket cards. A finished checkout does not clear recorded
blockers. Historical failures remain visible; later success must be assessed from
the retained evidence. A factory's normal process exit is labeled separately
from ticket completion.

Evidence links and recorded HTTP(S) pull request links open in new tabs. Local
files use `/api/evidence`, which serves only collected artifact links as bounded
plain text and rejects symlink paths. The launcher starts a compatible server
when an existing console lacks this endpoint.
The searchable Specs and artifacts library includes collected specifications,
tracker documents, role inputs and outputs, and receipts. Ticket cards provide
direct spec and recorded PR links. The file viewer supports copying and downloading
the original contents and formats JSON for reading. Workflow approval remains in
the existing version-bound workshop review controls.
Ticket cards link to the recorded tracker source URL for Jira or GitHub. When
the source is local, the card links to the collected source file or local record.
The interface checks server capability before displaying file links; an outdated
server displays an explicit update notice instead of broken viewer links.
Ticket timelines use the explicit stage markers in each tracker. Missing stage
evidence is not counted as progress. A resumed run labels its retained stage
as last recorded until new stage evidence arrives. Factory exit and finished
checkout ownership do not establish ticket completion; conflicting completion
and blocker records remain visible. Agent history, usage, and detailed run
observations are collapsed below the ticket and artifact views.
The separate Agents section reads sanitized factory and shared-dispatcher lifecycle records from
`.nightshift/agents/`, with role, provider, model, dispatcher PID and start/finish
times. A recorded running state may be stale after a hard kill; it is not an OS
heartbeat. Custom telemetry directories are intentionally not scanned as new roots.

The server serves fixed bundle paths and bounded local evidence APIs. It requires
an exact loopback Host and same-origin browser access, and enables no CORS.
Workshop specs can be read through `/api/workshop/reviews` and approved through
`POST /api/workshop/approve`. Approval requires a per-server token, explicit same-origin
Origin header, the current spec digest, identical canonical/project copies, and an
idle workshop lock. It writes a version-bound approval receipt and resumes the
saved workshop via fixed argv, retaining the original auth, model, and budgets.
The browser supplies no commands or runtime options. Concurrent approvals reuse
the launch receipt; a retained startup log records failures. API runs require the
dashboard process to have the original API key; there is no subscription fallback. Other mutation methods and arbitrary file paths are refused.
The shared collector bounds scanning, records and file sizes and reports truncation.

Runtime requires Git and Python 3.11+, but no Node, package install, CDN or paid provider.
The committed `dist/` bundle is rebuilt from `src/` using `npm ci && npm run build`
inside `dashboard/`; exact versions and integrity hashes are in package-lock.json.
`npm test` checks summary/filter semantics. Run `bash tests/test-dashboard-live.sh`
and `bash tests/test-dashboard.sh` from the checkout for API and static regressions.

Implementation references: `scripts/nightshift-dashboard.sh` (shared collector),
`dashboard/server.py` (transport), `dashboard/src/app.jsx` (reactive UI).
React effect cleanup follows https://react.dev/reference/react/useEffect;
local bundling uses https://esbuild.github.io/api/.

Factory workers also publish lifecycle records in the primary checkout before
launching the provider. The Agents section therefore shows startup activity even
before the first role dispatch. Success means the provider process exited cleanly;
use the run and gate evidence to determine whether the ticket is complete.

## Ticket actions

The **Continue a ticket** section offers **Resume** and **Clean up** for recorded
individual ticket runs. Resume performs safe artifact cleanup, then starts the
launcher with the recorded provider, authentication, base, and publication
settings. Clean up only reconciles artifacts. Neither action deletes files or
bypasses source-change or live-worker checks. Finished tickets cannot be resumed
from these controls.

Actions require the local origin, a server token, and the current saved-settings
hash. Repeat clicks reuse a live console launch. The console process must have
the same credentials as a terminal run; missing Jira credentials block before
any model starts. New terminal runs save only non-secret invocation settings.
