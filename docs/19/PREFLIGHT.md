# Issue 19 delivery preflight

Delivery target: integration/nightshift. Base remains 20aefa116003134f6464b2673ab11f8a06e9e353 after remote refresh.

Independent spec, code repair and drift review pass. Full offline verification passed 34 suites; final focused verification passed 16 sealed scanner cases plus preserved alias fixtures. Copy/symlink installs and audits pass through physical and macOS alias roots. Final source hashes and all failed attempts are retained in receipts.

The final implementation commit and PR must pass hosted CI, including ShellCheck, before merge. No main merge, active runtime update, production deployment, or Coach mutation is authorized by this preflight.

Untracked generated .nightshift.toml and scripts/__pycache__ remain preserved outside the delivery commit. The source audit explicitly excludes bytecode; local project configuration is outside its inventory.
