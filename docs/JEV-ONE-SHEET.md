# Jev One-Sheet

Status: reference summary. Repository sources are cited below; this sheet does not replace them.

## Purpose

Jev is an optional external evaluation service that Nightshift calls to judge one explicitly supplied evidence file against a typed rubric. Output is a receipt. It is shadow-only and cannot approve, pass, or fail any gate.

## Behavior

| Property | Value | Source |
|---|---|---|
| Role | Shadow evaluation; records judgments only | `docs/EFFICIENCY-ADAPTERS.md` |
| Gate authority | None. Cannot approve a gate or replace independent review | `docs/EFFICIENCY-ADAPTERS.md` |
| Failure handling | Missing credentials, malformed result, or outage produce an unavailable/skipped receipt; engineering gates still run | `docs/FOUNDRY-JEV-EPIC.md` |
| Default state | Enabled (`"enabled": true`) | `efficiency.json` |
| No input file | Writes a visible `NO_INPUT` skip; no network call; never searches for evidence | `docs/EFFICIENCY-ADAPTERS.md` |
| Routing | Not part of mandatory routing. Routing pilot (NJ-08) and gateway benchmark (NJ-09) are separate experiments | `docs/FOUNDRY-JEV-EPIC.md` |
| Azure/Foundry | Not a dependency | `docs/FOUNDRY-JEV-EPIC.md` |

## Configuration

Config lives in `efficiency.json`, `jev` section (installed as `nightshift-efficiency.json`).

| Field | Value |
|---|---|
| `endpoint` | `https://api.typesafe.ai/v1/systemone` |
| `model` | `jev-latest` |
| `key_env` | `TYPESAFE_API_KEY` (name of the environment variable holding the key) |
| `timeout_seconds` | 20 (total, including startup/DNS/TLS/body) |
| `max_bytes` | 262144 (256 KiB input/request/response) |
| `allow_loopback` | `false` |

- Override any field with `NIGHTSHIFT_JEV_<FIELD>` (for example `NIGHTSHIFT_JEV_ENABLED=false`, `NIGHTSHIFT_JEV_MODEL=...`). Lookup is by known field only: `scripts/nightshift-efficiency.py`.
- Credentials are environment references only; no secret values belong in configuration files.
- The credential variable is selected by `key_env`. To use a different variable, set `NIGHTSHIFT_JEV_KEY_ENV=<variable name>`.
- Transport: HTTPS required (HTTP only for explicitly allowed loopback fixtures), redirects rejected, no retries.

## Usage

```sh
nightshift evaluate --input ./approved-evidence.txt
nightshift evaluate --no-enabled
```

- Input can also be supplied via `NIGHTSHIFT_JEV_INPUT` (`scripts/nightshift-efficiency.py`).
- Only supply an approved file. Supplying it authorizes transmitting it to the configured endpoint, and the call may incur provider charges.
- To use from an agent: the agent's process must have the key variable in its environment, then run the command above.

## Receipts

- Location: `~/.nightshift/efficiency/<unique-id>/` by default; override with an absolute `NIGHTSHIFT_EFFICIENCY_DIR`. Directories 0700, files 0600.
- Stored: hashes, versioned rubric identity, validated typed judgments, selected/reported model, available usage, elapsed time.
- Never stored: request/response bodies, keys, server error content, invented cost or confidence.
- Missing usage or cost remains unknown. Byte reduction is not billed savings.
- Source: `docs/EFFICIENCY-ADAPTERS.md`, "Private evidence and accounting".

## Opt-out

- Per run: `nightshift evaluate --no-enabled`
- Environment: `NIGHTSHIFT_JEV_ENABLED=false`
- Project: `"enabled": false` in the `jev` section of the project efficiency config

## Evidence caveat

Vendor-published cost and latency results cover five weather-agent examples, not code-review accuracy. Shadow mode and independent labels are required before any judgment may affect work (`docs/FOUNDRY-JEV-EPIC.md`).

## Related documents

- `docs/EFFICIENCY-ADAPTERS.md`
- `docs/FOUNDRY-JEV-EPIC.md`
- `tests/test-jev-evaluation.py`
