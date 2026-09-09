# Dashboard startup

Terminal factory runs start or reuse the read-only loopback dashboard after
runtime preflight. The URL is printed before the coding runtime starts.
An isolated run without a local HEAD commit fails with BASE_MISSING before
setup or model execution. Bootstrap remains explicit; no starter files are
automatically staged, committed or pushed.
The browser opens only when a new dashboard process is started; reuse prints
the URL without spawning another tab. Automatic tab focusing is not attempted.

Use --dashboard off to disable automatic startup, or --dashboard-browser off
to retain the server without opening the browser. Environment equivalents are
NIGHTSHIFT_DASHBOARD=off and NIGHTSHIFT_DASHBOARD_BROWSER=off.
Project/global settings may use [dashboard] with mode = "auto" or "off" and
browser = "once" or "off". CLI/environment choices override configuration.

The preferred port is 8765. If another project or service owns it, an available
loopback port is selected and printed. An existing server is reused only after
checking its project identity. Per-project startup locks prevent duplicate
launches. Stale state causes a new process to be started, not an arbitrary PID
to be killed. Older dashboards can be identified through their state endpoint.

Dashboard state and private logs live under NIGHTSHIFT_HOME/dashboards. Startup
failure warns and does not fail the engineering ticket. The dashboard runs
independently of the terminal worker; it is not an operating-system login service.
A stopped dashboard is restarted on the next factory run, not continuously
supervised. The existing manual dashboard command remains available.

Implementation: scripts/nightshift-dashboard-start.py and dashboard/server.py.
