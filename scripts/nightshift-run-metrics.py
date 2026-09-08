#!/usr/bin/env python3
"""nightshift-run-metrics.py — shared typed run-metrics writer/validator.

One run-scoped, private metrics context per factory invocation, propagated to
role/worktree descendants through the environment (NIGHTSHIFT_RUN_ID,
NIGHTSHIFT_RUN_DIR). Every subcommand is defensive: metrics are strictly
observational, so any I/O or validation problem here is reported as a fixed,
nonfatal warning on stderr and the process still exits 0 — a metrics failure
must never fail (or appear to gate) the run it is describing.

Subcommands:
  init      Create <git-common-dir>/nightshift/runs/<run_id>/ and print
            {"run_id":..., "run_dir":..., "metrics_available": bool} for the
            caller to export. Without a Git common dir (no-Git project, or
            --branch none with no repository) metrics_available is false and
            run_dir is null: there is nowhere private and race-free to persist
            to, so the run gets a receipt on stdout only, never a best-effort
            write into the caller's working tree.
  event     Append one immutable, uniquely named observation or repair event.
            Allowlisted typed fields only; unknown properties are dropped by
            construction (the CLI only accepts named, validated flags).
  summary   Recompute and atomically replace summary.json from init's context
            plus every event recorded so far. Readers only ever see a
            complete summary.json (rename is atomic) or the previous one.

No prompts, transcripts, file paths, full commands, environment dumps,
stderr/stdout, or credential/header/cookie values are ever accepted as
metrics content — only the small typed fields enumerated below. Any string
field is scrubbed against currently-known credential environment values
before being written, as defense in depth; that scrub is not itself proof
that a field can never carry a secret; passing a syntactically-plain string
into a typed field is not proof it is one, and no capture is skipped merely
because it targets a hostile configuration — the same fixed logic applies.
"""
import argparse
import json
import os
import stat
import sys
import time
import uuid
import re
import fcntl
from pathlib import Path

SCHEMA_VERSION = 1

STAGES = {"product", "adversarial", "implement", "review", "drift", "preflight", "deploy"}
PROVIDERS = {"claude", "codex", "local"}
ROLES = {
    "nightshift-engineer", "nightshift-architect", "nightshift-code-fact-extractor",
    "nightshift-run-all-tests", "nightshift-spec-writer",
}
STATUSES = {"success", "failed", "interrupted"}
TERMINAL_STATUSES = {
    "running", "preflight_blocked", "provider_exited_0", "provider_exited_nonzero", "interrupted",
}
PREFLIGHT_REASONS = {
    "BASE_MISSING", "SPEC_INPUT_INVALID", "MANIFEST_MISSING", "MANIFEST_INVALID",
    "WORKTREE_COLLISION", "TASK_UNRESOLVED", "INPUT_RESOLUTION_REQUIRED",
    "BRANCH_POLICY_UNSUPPORTED", "USAGE",
}

# Field-specific string bounds. Generous enough for real values, small enough
# that nothing resembling a transcript, prompt, or path fits.
_BOUNDS = {"invocation_id": 128, "task": 128, "key": 64, "model": 128, "branch": 128}

# Known credential env values are redacted out of any string field, wherever
# they might appear, as a second line of defense behind the allowlist itself.
_CREDENTIAL_ENV_NAMES = (
    "OPENAI_API_KEY", "CODEX_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
    "JIRA_TOKEN", "MONDAY_TOKEN", "NOTION_TOKEN", "GH_TOKEN", "GITHUB_TOKEN",
)


def warn(msg):
    print(f"nightshift-run-metrics: warning: {msg}", file=sys.stderr)


def _redact(value):
    if not isinstance(value, str) or not value:
        return value
    out = value
    for name in _CREDENTIAL_ENV_NAMES:
        secret = os.environ.get(name, "")
        if secret and secret in out:
            out = out.replace(secret, "[REDACTED]")
    return out


def _bounded_str(value, field, max_len=64):
    if value is None:
        return None
    value = _redact(str(value))
    limit = _BOUNDS.get(field, max_len)
    return value if len(value) <= limit and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]*', value) else None


def _model(value):
    value = _bounded_str(value, 'model')
    if value is None:
        return None
    routing = Path(os.environ.get('NIGHTSHIFT_ROUTING_FILE', str(Path(__file__).resolve().parents[1] / 'routing.json')))
    def models(node):
        if isinstance(node, dict):
            if isinstance(node.get('model'), str):
                yield node['model']
            for child in node.values():
                yield from models(child)
        elif isinstance(node, list):
            for child in node:
                yield from models(child)
    try:
        return value if value in set(models(json.loads(routing.read_text()))) else None
    except (OSError, ValueError):
        return None


def _nonneg_int(value):
    if value is None:
        return None
    try:
        if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
            return None
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= 2**53 - 1 else None


def _finite_float(value):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):  # NaN check without importing math
        return None
    return f if f >= 0 else None


def _utc_now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _git_common_dir(project):
    import subprocess
    try:
        out = subprocess.check_output(
            ["git", "-C", project, "rev-parse", "--git-common-dir"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    common = out if out.startswith("/") else str(Path(project) / out)
    try:
        return str(Path(common).resolve(strict=True))
    except OSError:
        return None


def _owned_nonsymlink_dir(path):
    """Reject a symlinked context directory and require current-euid ownership."""
    p = Path(path)
    try:
        if p.is_symlink():
            return False
        st = os.stat(p, follow_symlinks=False)
        if not stat.S_ISDIR(st.st_mode):
            return False
        if hasattr(os, "geteuid") and st.st_uid != os.geteuid():
            return False
        return True
    except OSError:
        return False


def _atomic_write(path, data):
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
    tmp.chmod(0o600)
    os.replace(tmp, path)


def cmd_init(args):
    result = {"run_id": None, "run_dir": None, "metrics_available": False}
    run_id = uuid.uuid4().hex
    result["run_id"] = run_id
    # `--branch none` only skips isolation/worktree creation; a metrics home
    # under the Git common dir is still created whenever one exists.
    common = _git_common_dir(args.project)
    if common is None:
        warn("no Git common directory; run metrics persistence is unavailable (stdout receipt only)")
        print(json.dumps(result, sort_keys=True))
        return 0
    try:
        runs_root = Path(common) / "nightshift" / "runs"
        for directory in (Path(common) / "nightshift", runs_root):
            if directory.is_symlink():
                raise OSError('unsafe directory')
            directory.mkdir(mode=0o700, exist_ok=True)
            if not _owned_nonsymlink_dir(directory):
                raise OSError('unsafe directory')
        run_dir = runs_root / run_id
        run_dir.mkdir(mode=0o700, exist_ok=False)
        (run_dir / "events").mkdir(mode=0o700, exist_ok=True)
        if not _owned_nonsymlink_dir(run_dir):
            warn("invalid_run_directory")
            print(json.dumps(result, sort_keys=True))
            return 0
        context = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "start_monotonic": time.monotonic(),
            "start_wall": _utc_now_iso(),
        }
        _atomic_write(run_dir / "context.json", context)
        result["run_dir"] = str(run_dir)
        result["metrics_available"] = True
    except OSError as error:
        warn("run_directory_unavailable")
        result["run_dir"] = None
        result["metrics_available"] = False
    print(json.dumps(result, sort_keys=True))
    return 0


def _load_context(run_dir):
    run_dir = Path(run_dir)
    if not all(_owned_nonsymlink_dir(p) for p in (run_dir, run_dir.parent, run_dir.parent.parent)):
        return None
    context_path = run_dir / "context.json"
    try:
        if context_path.is_symlink():
            return None
        context = json.loads(context_path.read_text(encoding="utf-8"))
        if not isinstance(context, dict) or context.get('schema_version') != 1 or context.get('run_id') != run_dir.name:
            return None
        if _finite_float(context.get('start_monotonic')) is None:
            return None
        if os.environ.get('NIGHTSHIFT_RUN_ID', run_dir.name) != run_dir.name:
            return None
        return context
    except (OSError, ValueError):
        return None


def cmd_event(args):
    if not args.run_dir:
        warn("no run directory provided; event dropped")
        return 0
    context = _load_context(args.run_dir)
    if context is None:
        warn("invalid_run_context")
        return 0
    events_dir = Path(args.run_dir) / "events"
    try:
        events_dir.mkdir(mode=0o700, exist_ok=True)
        if not _owned_nonsymlink_dir(events_dir):
            raise OSError('unsafe events directory')
    except OSError as error:
        warn("events_directory_unavailable")
        return 0

    if args.kind == "observation":
        stage = args.stage if args.stage in STAGES else None
        if args.stage and stage is None:
            warn(f"dropping unknown stage: {_bounded_str(args.stage, 'stage')}")
        provider = args.provider if args.provider in PROVIDERS else None
        role = args.role if args.role in ROLES else None
        status = args.status if args.status in STATUSES else None
        record = {
            "kind": "observation",
            "invocation_id": _bounded_str(args.invocation_id, "invocation_id") or uuid.uuid4().hex,
            "stage": stage,
            "provider": provider,
            "model": _model(args.model),
            "selected_model": _model(args.model),
            "reported_model": None,
            "role": role,
            "duration_seconds": _finite_float(args.duration_seconds),
            "status": status,
            "usage": {
                "input_tokens": _nonneg_int(args.input_tokens),
                "output_tokens": _nonneg_int(args.output_tokens),
            },
            "recorded_at": _utc_now_iso(),
        }
    elif args.kind == "repair":
        old = _nonneg_int(args.old)
        new = _nonneg_int(args.new)
        delta = (new - old) if (old is not None and new is not None and new >= old) else None
        record = {
            "kind": "repair",
            "task": _bounded_str(args.task, "task"),
            "key": _bounded_str(args.key, "key"),
            "old": old,
            "new": new,
            "delta": delta,
            "recorded_at": _utc_now_iso(),
        }
    else:
        warn(f"unknown event kind: {args.kind}")
        return 0

    event_path = events_dir / f"{args.kind}-{uuid.uuid4().hex}.json"
    try:
        # Write-once, final filename: no reader can ever observe a partial
        # write under this name, and each event file is written exactly once.
        tmp = event_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
        tmp.chmod(0o600)
        os.replace(tmp, event_path)
    except OSError as error:
        warn("event_write_failed")
    return 0


def _read_events(run_dir):
    events_dir = Path(run_dir) / "events"
    events = []
    if not _owned_nonsymlink_dir(events_dir):
        return events
    for entry in sorted(events_dir.iterdir()):
        # Readers ignore temporary entries; only fully-renamed *.json files
        # are ever visible under a stable name.
        if entry.suffix != ".json" or entry.name.startswith(".") or entry.is_symlink():
            continue
        try:
            record = json.loads(entry.read_text(encoding="utf-8"))
            if not isinstance(record, dict):
                continue
            if record.get('kind') == 'repair':
                old, new = _nonneg_int(record.get('old')), _nonneg_int(record.get('new'))
                if old is not None and new is not None and new >= old:
                    events.append({'kind': 'repair', 'task': _bounded_str(record.get('task'), 'task'),
                                   'key': _bounded_str(record.get('key'), 'key'), 'old': old, 'new': new, 'delta': new-old})
            elif record.get('kind') == 'observation':
                usage = record.get('usage')
                usage = usage if isinstance(usage, dict) else {}
                events.append({'kind': 'observation', 'invocation_id': _bounded_str(record.get('invocation_id'), 'invocation_id'),
                               'stage': record.get('stage') if record.get('stage') in STAGES else None,
                               'provider': record.get('provider') if record.get('provider') in PROVIDERS else None,
                               'role': record.get('role') if record.get('role') in ROLES else None,
                               'model': _model(record.get('model')), 'duration_seconds': _finite_float(record.get('duration_seconds')),
                               'status': record.get('status') if record.get('status') in STATUSES else None,
                               'usage': {k: _nonneg_int(usage.get(k)) for k in ('input_tokens', 'output_tokens')}})
        except (OSError, ValueError):
            continue
    return events


def cmd_summary(args):
    if not args.run_dir:
        return _summary(args)
    context = _load_context(args.run_dir)
    if context is None or context['run_id'] != args.run_id:
        warn('invalid_run_context')
        return 0
    lock_path = Path(args.run_dir) / '.summary.lock'
    descriptor = os.open(lock_path, os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _summary(args)


def _summary(args):
    if args.terminal_status not in TERMINAL_STATUSES:
        warn(f"invalid terminal status: {_bounded_str(args.terminal_status, 'model')}")
        return 0
    preflight_reason = args.preflight_reason if args.preflight_reason in PREFLIGHT_REASONS else None
    if args.preflight_reason and preflight_reason is None:
        warn(f"dropping unknown preflight reason: {_bounded_str(args.preflight_reason, 'model')}")

    if not args.run_dir:
        warn("no run directory provided; summary not persisted")
        summary = {
            "schema_version": SCHEMA_VERSION, "run_id": args.run_id, "elapsed_seconds": None,
            "terminal_status": args.terminal_status, "preflight_reason": preflight_reason,
            "observations": [], "repair_count": None,
            "usage": {"input_tokens": None, "output_tokens": None, "complete": False},
        }
        print(json.dumps(summary, sort_keys=True))
        return 0

    context = _load_context(args.run_dir)
    if context is None:
        warn("invalid_run_context")
        return 0

    events = _read_events(args.run_dir)
    observations = list({e.get('invocation_id'): e for e in events
                         if e.get('kind') == 'observation' and _bounded_str(e.get('invocation_id'), 'invocation_id')}.values())
    repairs = list({(e.get('task'), e.get('key'), e.get('old'), e.get('new')): e for e in events
                    if e.get('kind') == 'repair' and _nonneg_int(e.get('delta')) is not None}.values())

    elapsed = time.monotonic() - context.get("start_monotonic", time.monotonic())

    # Zero repair events under an available, owned metrics context positively
    # proves zero repairs happened (nightshift-retry-increment.sh always
    # records one on every successful increment); it is not an absence of
    # evidence. A missing/invalid context is unknown, never assumed zero.
    complete_repairs = bool(repairs) and all(r.get("delta") is not None for r in repairs)
    repair_count = sum(r["delta"] for r in repairs) if complete_repairs else None

    usage_complete = len(observations) > 0 and all(
        o.get("usage", {}).get("input_tokens") is not None
        and o.get("usage", {}).get("output_tokens") is not None
        for o in observations
    )
    input_total = sum(
        o["usage"]["input_tokens"] for o in observations if o.get("usage", {}).get("input_tokens") is not None
    ) if observations else None
    output_total = sum(
        o["usage"]["output_tokens"] for o in observations if o.get("usage", {}).get("output_tokens") is not None
    ) if observations else None
    any_usage_reported = any(
        o.get("usage", {}).get("input_tokens") is not None or o.get("usage", {}).get("output_tokens") is not None
        for o in observations
    )
    if not any_usage_reported or not usage_complete:
        input_total = output_total = None

    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": context.get("run_id", args.run_id),
        "elapsed_seconds": round(elapsed, 3),
        "terminal_status": args.terminal_status,
        "preflight_reason": preflight_reason,
        "observations": [
            {
                "invocation_id": o.get("invocation_id"), "stage": o.get("stage"),
                "provider": o.get("provider"), "model": o.get("model"), "role": o.get("role"),
                "selected_model": o.get("model"), "reported_model": None,
                "duration_seconds": o.get("duration_seconds"), "status": o.get("status"),
                "usage": o.get("usage"),
            }
            for o in observations
        ],
        "repair_count": repair_count,
        "usage": {"input_tokens": input_total, "output_tokens": output_total, "complete": usage_complete},
    }
    try:
        _atomic_write(Path(args.run_dir) / "summary.json", summary)
    except OSError as error:
        warn("summary_write_failed")
    print(json.dumps(summary, sort_keys=True))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--project", required=True)
    p_init.add_argument("--branch", required=True)
    p_init.set_defaults(func=cmd_init)

    p_event = sub.add_parser("event")
    p_event.add_argument("--run-dir", default="")
    p_event.add_argument("--kind", required=True, choices=("observation", "repair"))
    p_event.add_argument("--invocation-id")
    p_event.add_argument("--stage")
    p_event.add_argument("--provider")
    p_event.add_argument("--model")
    p_event.add_argument("--role")
    p_event.add_argument("--duration-seconds")
    p_event.add_argument("--status")
    p_event.add_argument("--input-tokens")
    p_event.add_argument("--output-tokens")
    p_event.add_argument("--task")
    p_event.add_argument("--key")
    p_event.add_argument("--old")
    p_event.add_argument("--new")
    p_event.set_defaults(func=cmd_event)

    p_summary = sub.add_parser("summary")
    p_summary.add_argument("--run-dir", default="")
    p_summary.add_argument("--run-id", default=None)
    p_summary.add_argument("--terminal-status", required=True)
    p_summary.add_argument("--preflight-reason", default=None)
    p_summary.set_defaults(func=cmd_summary)

    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as error:  # noqa: BLE001 - metrics must never crash the caller
        warn(f"unexpected metrics failure: {type(error).__name__}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
