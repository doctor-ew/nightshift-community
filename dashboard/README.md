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
The separate Agents section reads sanitized shared-dispatcher lifecycle records from
`.nightshift/agents/`, with role, provider, model, dispatcher PID and start/finish
times. A recorded running state may be stale after a hard kill; it is not an OS
heartbeat. Custom telemetry directories are intentionally not scanned as new roots.

The Python standard-library server serves only fixed bundle paths and `/api/state`.
It accepts GET, exact loopback Host and same-origin browser access. No CORS, arbitrary
file, state mutation, control-plane or remote-binding endpoint is provided. Evidence
locations are displayed as text; opening files remains an explicit local operation.
The shared collector bounds scanning, records and file sizes and reports truncation.

Runtime requires Git and Python 3, but no Node, package install, CDN or paid provider.
The committed `dist/` bundle is rebuilt from `src/` using `npm ci && npm run build`
inside `dashboard/`; exact versions and integrity hashes are in package-lock.json.
`npm test` checks summary/filter semantics. Run `bash tests/test-dashboard-live.sh`
and `bash tests/test-dashboard.sh` from the checkout for API and static regressions.

Implementation references: `scripts/nightshift-dashboard.sh` (shared collector),
`dashboard/server.py` (transport), `dashboard/src/app.jsx` (reactive UI).
React effect cleanup follows https://react.dev/reference/react/useEffect;
local bundling uses https://esbuild.github.io/api/.
