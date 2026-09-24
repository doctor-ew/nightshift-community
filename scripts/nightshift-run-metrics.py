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
import hashlib
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
TICKET_SCHEMA_VERSION = 2

ATTRIBUTIONS = {"ticket", "shared", "unattributed"}
COVERAGE_SCOPES = {"self", "inclusive"}
CHILD_KINDS = {"none", "sdk_internal", "external_dispatch"}
USAGE_FIELDS = ("fresh_input", "cache_read_input", "cache_write_input", "output")
COST_FIELDS = (
    "provider_reported_estimate_usd", "token_derived_estimate_usd", "actual_billed_usd",
)

STAGES = {"product", "adversarial", "implement", "review", "drift", "preflight", "deploy"}
PROVIDERS = {"claude", "codex", "local"}
ROLES = {
    "nightshift-engineer", "nightshift-architect", "nightshift-code-fact-extractor",
    "nightshift-run-all-tests", "nightshift-spec-writer", "nightshift-behavior-reviewer",
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


def _canonical_json(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _typed_string(value, max_len=256, nullable=True):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value or len(value) > max_len:
        return None
    value = _redact(value)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/@+-]*", value):
        return None
    return value


def _ticket(value):
    if not isinstance(value, dict):
        return None
    source = _typed_string(value.get("source"), 64, False)
    repository = _typed_string(value.get("repository"), 256)
    source_id = _typed_string(value.get("source_id"), 256, False)
    if source is None or source_id is None:
        return None
    return {"source": source, "repository": repository, "source_id": source_id}


def _ticket_key(ticket):
    identity = [ticket["source"], ticket["repository"], ticket["source_id"]]
    encoded = json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _pricing_sources(value):
    if not isinstance(value, list):
        return []
    result = []
    string_fields = {"kind", "provider", "source", "version", "model"}
    allowed = string_fields | {"runtime_version", "normalizer_version"}
    for item in value:
        if not isinstance(item, dict) or any(key not in allowed for key in item):
            continue
        cleaned = {}
        for key in sorted(string_fields):
            typed = _typed_string(item.get(key), 256)
            if typed is not None:
                cleaned[key] = typed
        if "runtime_version" in item:
            runtime_version = item["runtime_version"]
            if runtime_version is None:
                cleaned["runtime_version"] = None
            else:
                typed = _typed_string(runtime_version, 256, False)
                if typed is not None:
                    cleaned["runtime_version"] = typed
        if "normalizer_version" in item:
            normalizer_version = _nonneg_int(item["normalizer_version"])
            if normalizer_version is not None:
                cleaned["normalizer_version"] = normalizer_version
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _stream_epoch(value):
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return str(value)
    return _typed_string(value, 128, False)


def _sanitize_receipt(value, expected_run_id):
    if not isinstance(value, dict) or value.get("schema_version") != TICKET_SCHEMA_VERSION:
        return None, "invalid_schema_version"
    run_id = _typed_string(value.get("run_id"), 128, False)
    invocation_id = _typed_string(value.get("invocation_id"), 128, False)
    receipt_id = _typed_string(value.get("receipt_id"), 128, False)
    sequence = _nonneg_int(value.get("sequence"))
    stream_epoch = _stream_epoch(value.get("stream_epoch"))
    if run_id != expected_run_id:
        return None, "run_id_mismatch"
    if invocation_id is None or receipt_id is None or sequence is None or stream_epoch is None:
        return None, "invalid_receipt_identity"

    attribution = value.get("attribution") if value.get("attribution") in ATTRIBUTIONS else None
    ticket = _ticket(value.get("ticket"))
    if attribution == "ticket" and ticket is None:
        attribution = "unattributed"
    if attribution != "ticket":
        ticket = None
    if attribution is None:
        attribution = "unattributed"

    included_value = value.get("included_invocation_ids")
    included = None
    if isinstance(included_value, list):
        included = []
        for item in included_value:
            cleaned = _typed_string(item, 128, False)
            if cleaned is not None and cleaned not in included:
                included.append(cleaned)

    usage_value = value.get("usage")
    usage = None
    if isinstance(usage_value, dict):
        usage = {field: _nonneg_int(usage_value.get(field)) for field in USAGE_FIELDS}
        usage["reasoning_output"] = _nonneg_int(usage_value.get("reasoning_output"))
        usage["total"] = _nonneg_int(usage_value.get("total"))

    cost_value = value.get("cost")
    cost = None
    if isinstance(cost_value, dict):
        cost = {field: _finite_float(cost_value.get(field)) for field in COST_FIELDS}
        cost["pricing_sources"] = _pricing_sources(cost_value.get("pricing_sources"))

    coverage_scope = value.get("coverage_scope")
    child_kind = value.get("child_kind")
    if coverage_scope not in COVERAGE_SCOPES or child_kind not in CHILD_KINDS:
        return None, "invalid_coverage_contract"

    record = {
        "schema_version": TICKET_SCHEMA_VERSION,
        "ticket": ticket,
        "attribution": attribution,
        "run_id": run_id,
        "invocation_id": invocation_id,
        "receipt_id": receipt_id,
        "sequence": sequence,
        "stream_epoch": stream_epoch,
        "provider": _typed_string(value.get("provider"), 64),
        "selected_model": _typed_string(value.get("selected_model"), 128),
        "reported_model": _typed_string(value.get("reported_model"), 128),
        "stage": _typed_string(value.get("stage"), 64),
        "status": value.get("status") if value.get("status") in STATUSES else None,
        "role": "orchestrator" if value.get("role") == "orchestrator" else _typed_string(value.get("role"), 128),
        "coverage_scope": coverage_scope,
        "parent_invocation_id": _typed_string(value.get("parent_invocation_id"), 128),
        "included_invocation_ids": included,
        "child_kind": child_kind,
        "usage": usage,
        "cost": cost,
    }
    return record, None


def _ensure_private_dir(path):
    if path.is_symlink():
        raise OSError("unsafe directory")
    path.mkdir(mode=0o700, exist_ok=True)
    if not _owned_nonsymlink_dir(path):
        raise OSError("unsafe directory")


def _immutable_write(path, data):
    encoded = (_canonical_json(data) + "\n").encode("utf-8")
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(tmp, path, follow_symlinks=False)
            return True
        except FileExistsError:
            return False
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def _ticket_dir(common, ticket, create):
    nightshift = Path(common) / "nightshift"
    root = nightshift / "ticket-metrics"
    directory = root / _ticket_key(ticket)
    if create:
        for item in (nightshift, root, directory, directory / "receipts"):
            _ensure_private_dir(item)
    return directory


def _usage_total(receipts):
    totals = {field: 0 for field in USAGE_FIELDS}
    observed = {field: False for field in USAGE_FIELDS}
    for receipt in receipts:
        usage = receipt.get("usage")
        if not isinstance(usage, dict):
            continue
        for field in USAGE_FIELDS:
            value = _nonneg_int(usage.get(field))
            if value is not None:
                totals[field] += value
                observed[field] = True
    if not any(observed.values()):
        return None
    result = {field: totals[field] if observed[field] else None for field in USAGE_FIELDS}
    result["total"] = sum(totals[field] for field in USAGE_FIELDS if observed[field])
    return result


def _cost_total(receipts):
    result = {}
    for field in COST_FIELDS:
        values = [receipt.get("cost", {}).get(field) for receipt in receipts
                  if isinstance(receipt.get("cost"), dict)
                  and _finite_float(receipt.get("cost", {}).get(field)) is not None]
        result[field] = round(sum(values), 12) if values else None
    sources = []
    for receipt in receipts:
        cost = receipt.get("cost")
        if not isinstance(cost, dict):
            continue
        for source in _pricing_sources(cost.get("pricing_sources")):
            if source not in sources:
                sources.append(source)
    result["pricing_sources"] = sources
    return result


def _empty_ticket_report(ticket, read_errors=0):
    return {
        "schema_version": TICKET_SCHEMA_VERSION,
        "ticket": ticket,
        "run_count": 0,
        "runs": [],
        "usage": {"known_subtotal": None, "nonadditive_observed": None, "complete": False},
        "cost": {**{field: None for field in COST_FIELDS}, "complete": False, "pricing_sources": []},
        "completeness": {
            "missing_usage_count": 0, "missing_model_count": 0, "missing_pricing_count": 0,
            "unmeasured_orchestrator_count": 0, "overlap_unknown_count": 0,
            "conflict_count": 0, "read_error_count": read_errors,
        },
        "breakdowns": {"stage": {}, "provider": {}, "reported_model": {}},
        "provenance": {"receipt_count": 0, "summary_rebuilt": False},
    }


def _read_ticket_receipts(directory, ticket):
    receipts = []
    errors = 0
    receipts_dir = directory / "receipts"
    if not receipts_dir.exists():
        return receipts, errors
    if not _owned_nonsymlink_dir(receipts_dir):
        return receipts, 1
    for entry in sorted(receipts_dir.iterdir()):
        if entry.suffix != ".json" or entry.name.startswith(".") or entry.is_symlink():
            continue
        try:
            raw = json.loads(entry.read_text(encoding="utf-8"))
            expected_run_id = raw.get("run_id") if isinstance(raw, dict) else None
            receipt, error = _sanitize_receipt(raw, expected_run_id)
            if error or receipt.get("ticket") != ticket or receipt.get("attribution") != "ticket":
                errors += 1
            else:
                receipts.append(receipt)
        except (OSError, ValueError):
            errors += 1
    return receipts, errors


def _deduplicate_receipts(receipts):
    exact = {}
    for receipt in receipts:
        payload = _canonical_json(receipt)
        exact.setdefault(payload, receipt)
    by_identity = {}
    for payload, receipt in exact.items():
        identity = (receipt["run_id"], receipt["invocation_id"], receipt["receipt_id"], receipt["sequence"])
        by_identity.setdefault(identity, []).append((payload, receipt))
    conflicts = sum(1 for values in by_identity.values() if len(values) > 1)
    clean = [values[0][1] for values in by_identity.values() if len(values) == 1]
    epochs = {}
    for receipt in clean:
        epoch = (receipt["run_id"], receipt["invocation_id"], receipt["receipt_id"], receipt["stream_epoch"])
        current = epochs.get(epoch)
        if current is None or receipt["sequence"] > current["sequence"]:
            epochs[epoch] = receipt
    return list(exact.values()), list(epochs.values()), conflicts


def _partition_overlap(receipts):
    parents = {(item["run_id"], item["invocation_id"]): item for item in receipts}
    explicitly_included = set()
    for parent in receipts:
        if parent.get("coverage_scope") != "inclusive":
            continue
        included = parent.get("included_invocation_ids")
        if isinstance(included, list):
            explicitly_included.update((parent["run_id"], child) for child in included)

    additive, uncertain = [], []
    for receipt in receipts:
        key = (receipt["run_id"], receipt["invocation_id"])
        if key in explicitly_included:
            continue
        parent_id = receipt.get("parent_invocation_id")
        parent = parents.get((receipt["run_id"], parent_id)) if parent_id else None
        if parent and parent.get("coverage_scope") == "inclusive":
            if receipt.get("child_kind") == "sdk_internal":
                continue
            included = parent.get("included_invocation_ids")
            if receipt.get("child_kind") == "external_dispatch" and included is None:
                uncertain.append(receipt)
                continue
        additive.append(receipt)
    return additive, uncertain


def _breakdowns(receipts):
    result = {"stage": {}, "provider": {}, "reported_model": {}}
    for dimension in result:
        buckets = {}
        for receipt in receipts:
            bucket = receipt.get(dimension) or "unknown"
            buckets.setdefault(bucket, []).append(receipt)
        for bucket, members in sorted(buckets.items()):
            result[dimension][bucket] = {
                "known_subtotal": _usage_total(members),
                "cost": _cost_total(members),
            }
    return result


def _build_ticket_report(directory, ticket):
    receipts, read_errors = _read_ticket_receipts(directory, ticket)
    provenance_receipts, latest, identity_conflicts = _deduplicate_receipts(receipts)
    additive, uncertain = _partition_overlap(latest)

    missing_usage = 0
    missing_model = 0
    missing_pricing = 0
    usage_conflicts = 0
    for receipt in additive:
        usage = receipt.get("usage")
        measured = isinstance(usage, dict) and any(_nonneg_int(usage.get(field)) is not None for field in USAGE_FIELDS)
        if not measured:
            missing_usage += 1
        else:
            missing_usage += sum(1 for field in USAGE_FIELDS if _nonneg_int(usage.get(field)) is None)
        if measured and all(_nonneg_int(usage.get(field)) is not None for field in USAGE_FIELDS):
            partition_total = sum(usage[field] for field in USAGE_FIELDS)
            supplied_total = _nonneg_int(usage.get("total"))
            if supplied_total is not None and supplied_total != partition_total:
                usage_conflicts += 1
        if receipt.get("reported_model") is None:
            missing_model += 1
        cost = receipt.get("cost") if isinstance(receipt.get("cost"), dict) else {}
        if _finite_float(cost.get("token_derived_estimate_usd")) is None:
            missing_pricing += 1

    run_ids = sorted({receipt["run_id"] for receipt in provenance_receipts})
    unmeasured_orchestrator = 0
    for run_id in run_ids:
        orchestrator = [receipt for receipt in provenance_receipts
                        if receipt["run_id"] == run_id and receipt.get("role") == "orchestrator"]
        if not any(_usage_total([receipt]) is not None for receipt in orchestrator):
            unmeasured_orchestrator += 1

    status_rank = {"success": 0, None: 1, "failed": 2, "interrupted": 3}
    runs = []
    for run_id in run_ids:
        members = [receipt for receipt in provenance_receipts if receipt["run_id"] == run_id]
        status = max((receipt.get("status") for receipt in members), key=lambda item: status_rank.get(item, 1))
        runs.append({"run_id": run_id, "status": status, "receipt_count": len(members)})

    conflicts = identity_conflicts + usage_conflicts
    complete = bool(additive) and not any((missing_usage, unmeasured_orchestrator,
                                           len(uncertain), conflicts, read_errors))
    costs = _cost_total(additive)
    cost_complete = bool(additive) and complete and all(costs[field] is not None for field in COST_FIELDS)
    report = {
        "schema_version": TICKET_SCHEMA_VERSION,
        "ticket": ticket,
        "run_count": len(run_ids),
        "runs": runs,
        "usage": {
            "known_subtotal": _usage_total(additive),
            "nonadditive_observed": _usage_total(uncertain),
            "complete": complete,
        },
        "cost": {**costs, "complete": cost_complete},
        "completeness": {
            "missing_usage_count": missing_usage,
            "missing_model_count": missing_model,
            "missing_pricing_count": missing_pricing,
            "unmeasured_orchestrator_count": unmeasured_orchestrator,
            "overlap_unknown_count": len(uncertain),
            "conflict_count": conflicts,
            "read_error_count": read_errors,
        },
        "breakdowns": _breakdowns(additive),
        "provenance": {"receipt_count": len(provenance_receipts), "summary_rebuilt": False},
    }
    try:
        _atomic_write(directory / "summary.json", report)
        report["provenance"]["summary_rebuilt"] = True
        _atomic_write(directory / "summary.json", report)
    except OSError:
        report["completeness"]["read_error_count"] += 1
        report["usage"]["complete"] = False
        report["cost"]["complete"] = False
    return report


def _accounting_result(ingested, reason=None, ticket_key=None):
    return {
        "schema_version": TICKET_SCHEMA_VERSION,
        "ingested": ingested,
        "available": ingested,
        "reason": reason,
        "ticket_key": ticket_key,
    }


def cmd_ingest(args):
    if not args.run_dir or not args.receipt_file:
        print(json.dumps(_accounting_result(False, "invalid_arguments"), sort_keys=True))
        return 64
    context = _load_context(args.run_dir)
    if context is None:
        print(json.dumps(_accounting_result(False, "invalid_run_context"), sort_keys=True))
        return 0
    try:
        receipt_path = Path(args.receipt_file)
        if receipt_path.is_symlink() or receipt_path.stat().st_size > 1024 * 1024:
            raise ValueError("invalid_receipt_file")
        raw = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(json.dumps(_accounting_result(False, "invalid_receipt_file"), sort_keys=True))
        return 0
    receipt, error = _sanitize_receipt(raw, context["run_id"])
    if error:
        print(json.dumps(_accounting_result(False, error), sort_keys=True))
        return 0

    payload_hash = hashlib.sha256(_canonical_json(receipt).encode("utf-8")).hexdigest()
    run_dir = Path(args.run_dir)
    try:
        events_dir = run_dir / "events"
        _ensure_private_dir(events_dir)
        _immutable_write(events_dir / f"accounting-{payload_hash}.json",
                         {"kind": "accounting_receipt", "receipt": receipt})
    except OSError:
        print(json.dumps(_accounting_result(False, "run_ledger_unavailable"), sort_keys=True))
        return 0

    ticket_key = None
    if receipt["attribution"] == "ticket":
        try:
            common = run_dir.parent.parent.parent
            if run_dir.parent.name != "runs" or run_dir.parent.parent.name != "nightshift":
                raise OSError("invalid run location")
            directory = _ticket_dir(common, receipt["ticket"], True)
            ticket_key = directory.name
            lock_descriptor = os.open(directory / ".lock", os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(lock_descriptor, "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                _immutable_write(directory / "receipts" / f"{payload_hash}.json", receipt)
                _build_ticket_report(directory, receipt["ticket"])
        except OSError:
            print(json.dumps(_accounting_result(False, "ticket_persistence_unavailable", ticket_key), sort_keys=True))
            return 0
    print(json.dumps(_accounting_result(True, ticket_key=ticket_key), sort_keys=True))
    return 0


def cmd_ticket_report(args):
    if not args.project or not args.source or args.repository is None or not args.source_id:
        print(json.dumps({"schema_version": TICKET_SCHEMA_VERSION, "error": "invalid_arguments"}, sort_keys=True))
        return 64
    repository = None if args.repository in ("", "null") else args.repository
    ticket = _ticket({"source": args.source, "repository": repository, "source_id": args.source_id})
    if ticket is None:
        print(json.dumps({"schema_version": TICKET_SCHEMA_VERSION, "error": "invalid_arguments"}, sort_keys=True))
        return 64
    common = _git_common_dir(args.project)
    if common is None:
        print(json.dumps(_empty_ticket_report(ticket, 1), sort_keys=True))
        return 0
    try:
        directory = _ticket_dir(common, ticket, True)
        descriptor = os.open(directory / ".lock", os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            report = _build_ticket_report(directory, ticket)
    except OSError:
        report = _empty_ticket_report(ticket, 1)
    print(json.dumps(report, sort_keys=True))
    return 0


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
            elif record.get('kind') == 'accounting_receipt':
                receipt, error = _sanitize_receipt(record.get('receipt'), Path(run_dir).name)
                if error is None:
                    events.append({'kind': 'accounting_receipt', 'receipt': receipt})
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
    accounting = [e['receipt'] for e in events if e.get('kind') == 'accounting_receipt']

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
        "accounting": {
            "receipt_count": len(accounting),
            "ticket_receipt_count": sum(1 for item in accounting if item.get('attribution') == 'ticket'),
            "shared_receipt_count": sum(1 for item in accounting if item.get('attribution') == 'shared'),
            "unattributed_receipt_count": sum(1 for item in accounting if item.get('attribution') == 'unattributed'),
        },
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

    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("--run-dir")
    p_ingest.add_argument("--receipt-file")
    p_ingest.set_defaults(func=cmd_ingest)

    p_ticket_report = sub.add_parser("ticket-report")
    p_ticket_report.add_argument("--project")
    p_ticket_report.add_argument("--source")
    p_ticket_report.add_argument("--repository")
    p_ticket_report.add_argument("--source-id")
    p_ticket_report.set_defaults(func=cmd_ticket_report)

    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as error:  # noqa: BLE001 - metrics must never crash the caller
        warn(f"unexpected metrics failure: {type(error).__name__}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
