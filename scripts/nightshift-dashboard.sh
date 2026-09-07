#!/usr/bin/env bash
# nightshift-dashboard.sh — read-only local HTML snapshot of Nightshift batch and gate
# state for a Git checkout and its registered worktrees.
#
# Renders a single, static HTML document to stdout from durable JSON already on disk
# (batch state, controller gate receipts, worktree ownership metadata). Never writes,
# never talks to a network, never invokes the controller or any factory process — a
# failure here cannot stop or alter a run. Redirect stdout to save a copy:
#
#   nightshift-dashboard.sh --project /path/to/repo > /tmp/nightshift-report.html
#
# Usage: nightshift-dashboard.sh [--project DIR]
#        nightshift-dashboard.sh --help

set -euo pipefail

print_help() {
  cat <<'USAGE'
Usage: nightshift-dashboard.sh [--project DIR]
       nightshift-dashboard.sh --help

Renders a static, read-only HTML snapshot of durable Nightshift batch status and
controller gate receipt JSON to stdout, sourced from the selected repository, its
registered Git worktrees, and their Nightshift state homes. Nothing is written to
disk and no network or control-plane call is made.

Options:
  --project DIR   Git checkout to inspect (default: current directory)
  --serve         Serve the reactive read-only dashboard at 127.0.0.1
  --port N        Loopback port (default: 8765; 0 selects an available port)
  --json          Emit the same bounded observations as JSON
  --static        Emit the standalone static snapshot (default)
  -h, --help      Show this help and exit

Save the report by redirecting stdout:

  nightshift-dashboard.sh --project /path/to/repo > /tmp/nightshift-report.html

Open the saved file directly in a browser (no server required).
USAGE
}

usage_error() {
  echo "nightshift-dashboard: $1" >&2
  echo "usage: nightshift-dashboard.sh [--project DIR]" >&2
  exit 64
}

PROJECT=""
MODE=static
PORT=8765
while [ "$#" -gt 0 ]; do
  case "$1" in
    --serve) MODE=serve; shift ;;
    --json) MODE=json; shift ;;
    --static) MODE=static; shift ;;
    --port) [ "$#" -ge 2 ] || usage_error '--port requires a number'; PORT="$2"; shift 2 ;;
    --project)
      [ "$#" -ge 2 ] && [ -n "${2:-}" ] || usage_error "--project requires a directory"
      PROJECT="$2"
      shift 2
      ;;
    -h|--help)
      print_help
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      usage_error "unknown option: $1"
      ;;
    *)
      usage_error "unexpected argument: $1"
      ;;
  esac
done
[ "$#" -eq 0 ] || usage_error "unexpected argument: $1"

[ -n "$PROJECT" ] || PROJECT="$(pwd)"
[ -d "$PROJECT" ] || { echo "nightshift-dashboard: not a directory: $PROJECT" >&2; exit 66; }
PROJECT="$(cd "$PROJECT" && pwd -P)" || { echo "nightshift-dashboard: cannot resolve project directory" >&2; exit 66; }

command -v git >/dev/null 2>&1 || { echo "nightshift-dashboard: git is required" >&2; exit 69; }
command -v python3 >/dev/null 2>&1 || { echo "nightshift-dashboard: python3 is required" >&2; exit 69; }

git -C "$PROJECT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "nightshift-dashboard: not a Git repository: $PROJECT" >&2
  exit 66
}

ROOT="$(git -C "$PROJECT" rev-parse --show-toplevel)" || {
  echo "nightshift-dashboard: cannot resolve repository root for $PROJECT" >&2
  exit 66
}
ROOT="$(cd "$ROOT" && pwd -P)"

if [ "$MODE" = serve ]; then
  case "$PORT" in ''|*[!0-9]*) usage_error 'invalid port';; esac
  [ "${#PORT}" -le 5 ] && [ "$PORT" -le 65535 ] || usage_error 'invalid port'
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  exec python3 "$SCRIPT_DIR/../dashboard/server.py" --project "$ROOT" --port "$PORT"
fi

COMMON="$(git -C "$ROOT" rev-parse --git-common-dir)" || {
  echo "nightshift-dashboard: cannot resolve Git common directory" >&2
  exit 66
}
case "$COMMON" in
  /*) ;;
  *) COMMON="$ROOT/$COMMON" ;;
esac
COMMON="$(cd "$COMMON" && pwd -P)" || {
  echo "nightshift-dashboard: cannot resolve Git common directory" >&2
  exit 66
}

WORKTREES=()
while IFS= read -r line; do
  case "$line" in
    "worktree "*)
      wt="${line#worktree }"
      [ -d "$wt" ] || continue
      wt="$(cd "$wt" && pwd -P)" || continue
      WORKTREES+=("$wt")
      ;;
  esac
done < <(git -C "$ROOT" worktree list --porcelain)
[ "${#WORKTREES[@]}" -gt 0 ] || WORKTREES=("$ROOT")

GENERATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

NIGHTSHIFT_DASHBOARD_FORMAT="$MODE" exec python3 - "$ROOT" "$COMMON" "$GENERATED_AT" "${WORKTREES[@]}" <<'NIGHTSHIFT_DASHBOARD_PY_EOF'
import html
import itertools
import json
import os
import re
import stat
import sys
import urllib.parse

# --- driver arguments (already canonicalized, physical paths from bash + git) -------

if len(sys.argv) < 4:
    sys.stderr.write("nightshift-dashboard: internal error: missing driver arguments\n")
    sys.exit(70)

ROOT = sys.argv[1]
COMMON = sys.argv[2]
GENERATED_AT = sys.argv[3]
WORKTREES = list(dict.fromkeys(sys.argv[4:]))

# --- bounds ---------------------------------------------------------------------------

MAX_FILE_BYTES = 1_048_576
MAX_ENTRIES_PER_DIR = 500
MAX_TOTAL_RECORDS = 1000
MAX_SCAN_ENTRIES = 10000
MAX_DEPTH = 6
scan_entries = 0

STATE_HOME_NAMES = (".nightshift", ".drew", os.path.join(".claude", "task-progress"))
ACTIVE_STATUSES = {"pending", "in_progress", "running"}
TERMINAL_STATUSES = {"complete", "skipped", "failed", "blocked", "needs-decision"}
OWNERSHIP_STATUSES = {"prepared", "finished"}
BATCH_NAME_RE = re.compile(r"^batch-[0-9]+-[0-9]+\.json$")

warnings = []
error_rows = []
data_rows = []
total_records = 0
_truncated_dirs = set()


def note_truncation(where):
    if where in _truncated_dirs:
        return
    _truncated_dirs.add(where)
    warnings.append("Bounded scan stopped early under %s (entry/record cap reached)." % where)


def real(path):
    try:
        return os.path.realpath(path)
    except (OSError, ValueError):
        return None


def within(path_real, roots_real):
    for r in roots_real:
        if path_real == r or path_real.startswith(r + os.sep):
            return True
    return False


ROOT_REAL = real(ROOT) or ROOT
COMMON_REAL = real(COMMON) or COMMON
CHECKOUTS = list(dict.fromkeys([ROOT] + WORKTREES))

checkout_reals = {}
for c in CHECKOUTS:
    cr = real(c)
    if cr and os.path.isdir(cr):
        checkout_reals[c] = cr


def safe_listdir(dir_path, allowed_roots):
    """Direct children of dir_path. Symlinked entries resolving outside
    allowed_roots are dropped — never followed, never used as new roots."""
    global scan_entries
    if scan_entries >= MAX_SCAN_ENTRIES:
        return [], True
    limit = min(MAX_ENTRIES_PER_DIR, MAX_SCAN_ENTRIES - scan_entries)
    try:
        with os.scandir(dir_path) as it:
            raw = list(itertools.islice(it, limit + 1))
    except OSError as exc:
        warnings.append("Cannot scan %s: %s" % (dir_path, exc))
        return [], False
    scan_entries += min(len(raw), limit)
    hit_cap = len(raw) > limit
    kept = []
    for entry in raw[:limit]:
        try:
            if entry.is_symlink():
                target_real = real(entry.path)
                if not target_real or not within(target_real, allowed_roots):
                    continue
            kept.append(entry)
        except OSError:
            continue
    return kept, hit_cap


def read_bounded(path):
    """Return (text, error). Never raises. `path` must already be vetted as
    inside an allowed root by the caller (this only bounds size/type/IO)."""
    # Pin every ancestor with no-follow descriptors. Validating realpath before
    # plain open() permits a symlink-retarget race while the live server collects.
    absolute = os.path.abspath(path)
    if not within(absolute, ARTIFACT_ROOTS):
        return None, "outside artifact roots"
    directory = None
    descriptor = None
    try:
        directory = os.open(os.sep, os.O_RDONLY | os.O_DIRECTORY)
        parts = absolute.split(os.sep)[1:]
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=directory)
            os.close(directory)
            directory = child
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=directory)
        st = os.fstat(descriptor)
        if not stat.S_ISREG(st.st_mode):
            return None, "not a regular file"
        if st.st_size > MAX_FILE_BYTES:
            return None, "oversized (%d bytes > %d byte cap)" % (st.st_size, MAX_FILE_BYTES)
        with os.fdopen(descriptor, "r", encoding="utf-8") as fh:
            descriptor = None
            data = fh.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            return None, "oversized (exceeds %d byte cap)" % MAX_FILE_BYTES
        return data, None
    except (OSError, UnicodeDecodeError) as exc:
        return None, "unreadable (%s)" % exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory is not None:
            os.close(directory)


def as_str(v):
    return v if isinstance(v, str) else None


def as_int_strict(v):
    if isinstance(v, bool):
        return None
    return v if isinstance(v, int) and v >= 0 else None


def as_list(v):
    return v if isinstance(v, list) else None


def as_dict(v):
    return v if isinstance(v, dict) else None


def resolve_link(checkout, allowed_roots, raw_path):
    """Resolve `raw_path` (untrusted string found inside a JSON file) to an
    existing regular file within allowed_roots, or None. This only checks
    existence of a single file — it is never used to open a directory for
    further discovery."""
    if not isinstance(raw_path, str) or not raw_path:
        return None
    if "\x00" in raw_path or ".." in raw_path.split(os.sep) or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", raw_path):
        return None
    candidate = raw_path if os.path.isabs(raw_path) else os.path.join(checkout, raw_path)
    cr = real(candidate)
    if not cr or not within(cr, allowed_roots):
        return None
    if not os.path.isfile(cr):
        return None
    return cr


def file_uri(path):
    return "file://" + urllib.parse.quote(path, safe="/")


def make_link(label, path):
    resolved = resolve_link(ROOT, ARTIFACT_ROOTS, path)
    try:
        return {"label": label, "href": file_uri(resolved), "modified_at": os.stat(resolved).st_mtime} if resolved else None
    except (UnicodeError, OSError):
        return None  # Non-UTF-8 filesystem names cannot form a safe URI.


def state_bucket(status):
    if status in ACTIVE_STATUSES:
        return "active"
    if status in TERMINAL_STATUSES:
        return "terminal"
    return "unknown"


def add_error_row(ticket, source, checkout, path, message):
    links = []
    if path:
        try:
            if os.path.isfile(path):
                links = [make_link(os.path.basename(path), path)]
        except OSError:
            pass
    error_rows.append({
        "ticket": ticket or "unknown",
        "source": source,
        "checkout": checkout,
        "message": message,
        "links": links,
    })


def display_status(value):
    status = as_str(value)
    return status if status in ACTIVE_STATUSES | TERMINAL_STATUSES else "unknown (invalid or missing status)"


def deferred_text(record):
    value = record.get("deferred_decisions")
    if value is None:
        return ""
    if isinstance(value, (str, list, dict)):
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=True)
    return "unknown (invalid deferred_decisions)"


def retry_fields(receipt):
    attempts = as_list(receipt.get("attempts"))
    budget = as_int_strict(receipt.get("repair_budget"))
    attempted = None
    if attempts is not None:
        attempted = 0
        for a in attempts:
            d = as_dict(a)
            if d is None:
                attempted = None
                break
            if "attempt" in d:
                if as_int_strict(d["attempt"]) is None:
                    attempted = None
                    break
                attempted += 1
            elif as_int_strict(d.get("repair_after_attempt")) is None:
                attempted = None
                break
    remaining = None
    if attempted is not None and budget is not None:
        remaining = max(0, budget - attempted)
    return tuple(str(v) if v is not None else "unknown" for v in (attempted, budget, remaining))


def build_gate_row(ticket_hint, receipt, checkout, source_path):
    ticket = as_str(receipt.get("ticket")) or ticket_hint or "unknown"
    status = display_status(receipt.get("status"))
    gate = as_str(receipt.get("gate")) or as_str(receipt.get("stage"))
    flavor = None
    if gate is None:
        failed_gate = as_str(receipt.get("failed_gate"))
        if failed_gate is not None:
            gate = failed_gate
            flavor = "human-authored (failed_gate)"
    if gate is None:
        gate = "unknown"
    provider = as_str(receipt.get("provider")) or "unknown"
    worktree = as_str(receipt.get("worktree")) or "unknown"
    attempted, budget, remaining = retry_fields(receipt)
    return {
        "ticket": ticket,
        "source": "gate",
        "checkout": checkout,
        "state": status,
        "state_bucket": state_bucket(status),
        "gate": gate,
        "flavor": flavor,
        "provider": provider,
        "worktree": worktree,
        "attempted": attempted,
        "budget": budget,
        "remaining": remaining,
        "reason": as_str(receipt.get("reason")) or "",
        "deferred_decisions": deferred_text(receipt),
        "next_action": as_str(receipt.get("next_action")) or "",
        "pr_url_text": None,
        "links": [make_link(os.path.basename(source_path), source_path)],
    }


def handle_batch_file(path, checkout, allowed_roots):
    global total_records
    if total_records >= MAX_TOTAL_RECORDS:
        note_truncation(path)
        return
    total_records += 1
    text, err = read_bounded(path)
    if err:
        add_error_row(None, "batch", checkout, path, "%s: %s" % (os.path.basename(path), err))
        return
    try:
        obj = json.loads(text)
    except (ValueError, RecursionError) as exc:
        add_error_row(None, "batch", checkout, path, "malformed JSON in %s: %s" % (os.path.basename(path), exc))
        return
    d = as_dict(obj)
    if d is None or as_str(d.get("batch_id")) is None or as_dict(d.get("statuses")) is None:
        add_error_row(None, "batch", checkout, path,
                      "%s: wrong shape (expected object with batch_id/statuses)" % os.path.basename(path))
        return
    batch_id = d["batch_id"]
    statuses = d["statuses"]
    for ticket, entry in statuses.items():
        if total_records >= MAX_TOTAL_RECORDS:
            note_truncation("batch %s in %s" % (batch_id, path))
            return
        total_records += 1
        entry_d = as_dict(entry)
        if entry_d is None:
            add_error_row(ticket, "batch", checkout, path,
                          "batch %s: ticket %s has a non-object status entry" % (batch_id, ticket))
            continue
        status = display_status(entry_d.get("status"))
        reason = as_str(entry_d.get("reason")) or ""
        pr_url_raw = entry_d.get("pr_url")
        receipt_raw = entry_d.get("receipt")
        links = [make_link("%s (batch %s)" % (os.path.basename(path), batch_id), path)]
        next_action = as_str(entry_d.get("next_action")) or ""
        if receipt_raw is not None:
            resolved = resolve_link(checkout, allowed_roots, receipt_raw)
            if resolved:
                links.append(make_link("source receipt", resolved))
            else:
                next_action += " [receipt referenced but not a valid local artifact]"
        pr_text = pr_url_raw if isinstance(pr_url_raw, str) else None
        attempted, budget, remaining = retry_fields(entry_d)
        data_rows.append({
            "ticket": ticket,
            "source": "batch",
            "checkout": checkout,
            "state": status,
            "state_bucket": state_bucket(status),
            "gate": as_str(entry_d.get("gate")) or as_str(entry_d.get("stage")) or as_str(entry_d.get("failed_gate")) or "unknown",
            "flavor": None,
            "provider": as_str(entry_d.get("provider")) or "unknown",
            "worktree": as_str(entry_d.get("worktree")) or "unknown",
            "attempted": attempted,
            "budget": budget,
            "remaining": remaining,
            "reason": reason,
            "deferred_decisions": deferred_text(entry_d),
            "next_action": next_action,
            "pr_url_text": pr_text,
            "links": links,
        })


def classify_and_handle_json(path, checkout, ticket_hint, state_record=False):
    """Shape-sniff a *.json file that is not batch-named: gate/task receipt
    (has `ticket` and `gate`/`failed_gate`/`status`), or quietly not a
    dashboard source at all."""
    global total_records
    if total_records >= MAX_TOTAL_RECORDS:
        note_truncation(os.path.dirname(path))
        return
    text, err = read_bounded(path)
    if err:
        # Any *.json file under a discovery root is a candidate structured
        # record — unreadable/oversized ones are reported, never dropped.
        total_records += 1
        add_error_row(ticket_hint, "gate", checkout, path, "%s: %s" % (os.path.basename(path), err))
        return
    try:
        obj = json.loads(text)
    except (ValueError, RecursionError) as exc:
        total_records += 1
        add_error_row(ticket_hint, "gate", checkout, path,
                      "malformed JSON in %s: %s" % (os.path.basename(path), exc))
        return
    d = as_dict(obj)
    if d is None:
        total_records += 1
        add_error_row(ticket_hint, "state", checkout, path, "wrong shape: expected JSON object")
        return
    if os.path.dirname(path) == os.path.join(checkout, ".nightshift", "agents"):
        total_records += 1
        role = as_str(d.get("role"))
        status = as_str(d.get("status"))
        if not role or status not in {"running", "success", "failed", "interrupted"} or as_int_strict(d.get("pid")) is None:
            add_error_row(role, "agent", checkout, path, "invalid agent lifecycle record")
            return
        data_rows.append({"ticket": role, "source": "agent", "checkout": checkout,
            "state": status, "state_bucket": "active" if status == "running" else "terminal",
            "gate": role, "provider": as_str(d.get("provider")) or "unknown",
            "model": as_str(d.get("model")) or "unknown", "pid": d["pid"],
            "started_at": as_str(d.get("started_at")) or "unknown",
            "finished_at": as_str(d.get("finished_at")) or "", "worktree": checkout,
            "flavor": "dispatcher lifecycle", "pr_url_text": None, "deferred_decisions": "",
            "attempted": "unknown", "budget": "unknown", "remaining": "unknown",
            "reason": "Recorded dispatcher lifecycle; not an OS heartbeat.",
            "next_action": "", "links": [make_link(os.path.basename(path), path)]})
        return
    if as_str(d.get("batch_id")) is not None and as_dict(d.get("statuses")) is not None:
        handle_batch_file(path, checkout, ARTIFACT_ROOTS)
        return
    ticket_present = "ticket" in d
    gate_present = "gate" in d or "failed_gate" in d
    status_present = "status" in d
    if not (ticket_present and (gate_present or status_present)):
        if state_record:
            total_records += 1
            add_error_row(ticket_hint, "state", checkout, path, "wrong shape: expected batch or ticket receipt")
        return
    total_records += 1
    if as_str(d.get("ticket")) is None or as_str(d.get("status")) is None:
        add_error_row(as_str(d.get("ticket")) or ticket_hint, "gate", checkout, path,
                      "%s: wrong shape (ticket/status must be strings)" % os.path.basename(path))
        return
    data_rows.append(build_gate_row(ticket_hint, d, checkout, path))


def handle_ownership_file(path, checkout_label):
    global total_records
    if total_records >= MAX_TOTAL_RECORDS:
        note_truncation(os.path.dirname(path))
        return
    total_records += 1
    text, err = read_bounded(path)
    if err:
        add_error_row(None, "ownership", checkout_label, path, "%s: %s" % (os.path.basename(path), err))
        return
    try:
        obj = json.loads(text)
    except (ValueError, RecursionError) as exc:
        add_error_row(None, "ownership", checkout_label, path,
                      "malformed JSON in %s: %s" % (os.path.basename(path), exc))
        return
    d = as_dict(obj)
    if d is None:
        add_error_row(None, "ownership", checkout_label, path,
                      "%s: wrong shape (expected object)" % os.path.basename(path))
        return
    task = as_str(d.get("task")) or "unknown"
    status = as_str(d.get("status"))
    if status in OWNERSHIP_STATUSES:
        state_display = status
    elif status:
        state_display = "unknown (unexpected status: " + status + ")"
    else:
        state_display = "unknown"
    branch = as_str(d.get("branch")) or "unknown"
    worktree = as_str(d.get("worktree")) or "unknown"
    base_ref = as_str(d.get("base_ref")) or "unknown"
    dependency = as_str(d.get("dependency")) or ""
    data_rows.append({
        "ticket": task,
        "source": "ownership",
        "checkout": checkout_label,
        "state": state_display,
        "state_bucket": "ownership",
        "gate": "unknown",
        "flavor": None,
        "provider": "unknown",
        "worktree": worktree,
        "attempted": "unknown",
        "budget": "unknown",
        "remaining": "unknown",
        "reason": ("depends on " + dependency) if dependency else "",
        "next_action": "branch %s @ base %s" % (branch, base_ref),
        "pr_url_text": None,
        "links": [make_link(os.path.basename(path), path)],
    })


# --- discovery: exact artifact roots; bounded recursive scans ----------------------

def known_root(path):
    # A symlink cannot redefine a known root as checkout secrets or Git internals.
    resolved = real(path)
    expected = os.path.abspath(path)
    return resolved if resolved == expected and os.path.isdir(resolved) else None


ARTIFACT_ROOTS = []
for checkout in checkout_reals:
    for name in STATE_HOME_NAMES + ("docs",):
        root = known_root(os.path.join(checkout, name))
        if root:
            ARTIFACT_ROOTS.append(root)
ownership_dir = known_root(os.path.join(COMMON, "nightshift", "worktrees"))
if ownership_dir:
    ARTIFACT_ROOTS.append(ownership_dir)


def walk_files(directory, roots, depth=0, visited=None):
    if visited is None:
        visited = set()
    resolved = real(directory)
    if not resolved or not within(resolved, roots) or resolved in visited:
        return
    visited.add(resolved)
    entries, hit_cap = safe_listdir(directory, roots)
    if hit_cap:
        note_truncation(directory)
    for entry in entries:
        try:
            if entry.is_dir():
                if depth >= MAX_DEPTH:
                    note_truncation(entry.path)
                else:
                    yield from walk_files(entry.path, roots, depth + 1, visited)
            else:
                # Include disappeared/unreadable JSON candidates for per-record errors.
                yield entry.path
        except OSError as exc:
            add_error_row(None, "discovery", directory, entry.path, str(exc))


for checkout in checkout_reals:
    for name in STATE_HOME_NAMES:
        state_dir = known_root(os.path.join(checkout, name))
        if not state_dir:
            continue
        for path in walk_files(state_dir, [state_dir]):
            if BATCH_NAME_RE.match(os.path.basename(path)):
                handle_batch_file(path, checkout, ARTIFACT_ROOTS)
            elif path.endswith(".json"):
                classify_and_handle_json(path, checkout, None, state_record=True)

    docs_dir = known_root(os.path.join(checkout, "docs"))
    if docs_dir:
        entries, hit_cap = safe_listdir(docs_dir, [docs_dir])
        if hit_cap:
            note_truncation(docs_dir)
        for task_entry in entries:
            try:
                if not task_entry.is_dir():
                    continue
            except OSError as exc:
                add_error_row(task_entry.name, "artifacts", checkout, task_entry.path, str(exc))
                continue
            task_links = []
            for path in walk_files(task_entry.path, [docs_dir]):
                link = make_link(os.path.relpath(path, task_entry.path), path)
                if link:
                    task_links.append(link)
                if path.endswith(".json"):
                    classify_and_handle_json(path, checkout, task_entry.name)
            if task_links:
                if total_records >= MAX_TOTAL_RECORDS:
                    note_truncation(task_entry.path)
                    continue
                total_records += 1
                row = build_gate_row(task_entry.name, {}, checkout, task_entry.path)
                row.update(source="artifacts", state="n/a", state_bucket="artifacts", links=task_links)
                data_rows.append(row)

if ownership_dir:
    for path in walk_files(ownership_dir, [ownership_dir]):
        if path.endswith(".json") and not path.endswith("-migration.json"):
            handle_ownership_file(path, "(shared repository metadata)")

# --- render ----------------------------------------------------------------------------


def esc(v):
    text = "" if v is None else str(v)
    text = re.sub(r"[\ud800-\udfff]", "[invalid Unicode surrogate]", text)
    return html.escape(text, quote=True)


def render_links(links):
    links = [link for link in links if link]
    if not links:
        return '<span class="muted">none</span>'
    return " &middot; ".join('<a href="%s">%s</a>' % (esc(l["href"]), esc(l["label"])) for l in links)


def rel_label(path):
    if path == ROOT:
        return "."
    if not os.path.isabs(path):
        return path  # synthetic labels (e.g. shared metadata root), not a filesystem path
    try:
        r = os.path.relpath(path, ROOT)
    except ValueError:
        r = path
    return r


data_rows.sort(key=lambda r: (r["ticket"], r["source"], r["checkout"]))
error_rows.sort(key=lambda r: (r["ticket"], r["source"], r["checkout"]))

if os.environ.get("NIGHTSHIFT_DASHBOARD_FORMAT") == "json":
    # Same collector and bounds as static mode; no separate filesystem API.
    sys.stdout.write(json.dumps({"generated_at": GENERATED_AT, "root": ROOT,
        "checkouts": list(checkout_reals), "rows": data_rows,
        "errors": error_rows, "warnings": warnings}, ensure_ascii=True))
    sys.exit(0)

body_parts = []
body_parts.append("<h1>Nightshift Dashboard</h1>")
body_parts.append("<p>Read-only static snapshot. Generated %s. Selected repository root: <code>%s</code>. "
                   "No writes, no network access, no controller invocation happened to produce this page.</p>"
                   % (esc(GENERATED_AT), esc(ROOT)))

checkout_list = "".join("<li><code>%s</code></li>" % esc(rel_label(c)) for c in checkout_reals)
body_parts.append("<h2>Checkouts scanned</h2><ul>%s</ul>" % checkout_list)

if warnings:
    items = "".join("<li>%s</li>" % esc(w) for w in warnings)
    body_parts.append('<h2 id="warnings">Warnings</h2><ul class="warnings">%s</ul>' % items)

if not data_rows and not error_rows:
    body_parts.append(
        '<p class="empty">No batch status, gate receipt, or ownership records were found under the '
        "scanned checkouts. This is an empty snapshot, not a failure.</p>"
    )
else:
    if data_rows:
        rows_html = []
        for row in data_rows:
            flavor_html = (' <span class="tag">%s</span>' % esc(row["flavor"])) if row.get("flavor") else ""
            pr_html = ('<div class="muted">pr: %s</div>' % esc(row["pr_url_text"])) if row.get("pr_url_text") else ""
            deferred_bits = []
            if row.get("reason"):
                deferred_bits.append("reason: %s" % esc(row["reason"]))
            if row.get("next_action"):
                deferred_bits.append("next: %s" % esc(row["next_action"]))
            if row.get("deferred_decisions"):
                deferred_bits.append("deferred decisions: %s" % esc(row["deferred_decisions"]))
            deferred_html = "<br>".join(deferred_bits) if deferred_bits else '<span class="muted">none</span>'
            rows_html.append(
                "<tr>"
                "<th scope=\"row\">%s</th>"
                "<td>%s</td>"
                "<td>%s</td>"
                "<td>%s%s%s</td>"
                "<td>%s</td>"
                "<td>%s</td>"
                "<td>%s</td>"
                "<td>%s / %s <span class=\"muted\">(remaining %s)</span></td>"
                "<td>%s</td>"
                "<td>%s</td>"
                "</tr>" % (
                    esc(row["ticket"]), esc(row["source"]), esc(rel_label(row["checkout"])),
                    esc(row["state"]), flavor_html, pr_html,
                    esc(row["gate"]), esc(row["provider"]), esc(row["worktree"]),
                    esc(row["attempted"]), esc(row["budget"]), esc(row["remaining"]),
                    deferred_html, render_links(row["links"]),
                )
            )
        body_parts.append(
            "<h2>Observations</h2>"
            '<table><caption>Batch, gate, ownership, and artifact observations. Each row is one '
            "source file's own claim &mdash; a terminal batch entry does not overwrite an active "
            "gate receipt for the same ticket, and vice versa.</caption>"
            "<thead><tr>"
            '<th scope="col">Ticket / Run</th><th scope="col">Source</th><th scope="col">Checkout</th>'
            '<th scope="col">State</th><th scope="col">Gate</th><th scope="col">Provider</th>'
            '<th scope="col">Worktree</th><th scope="col">Retry (used / budget)</th>'
            '<th scope="col">Deferred</th><th scope="col">Links</th>'
            "</tr></thead><tbody>%s</tbody></table>" % "".join(rows_html)
        )

    if error_rows:
        err_html = []
        for row in error_rows:
            err_html.append(
                "<tr><th scope=\"row\">%s</th><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                    esc(row["ticket"]), esc(row["source"]), esc(rel_label(row["checkout"])),
                    esc(row["message"]), render_links(row["links"]),
                )
            )
        body_parts.append(
            "<h2>Errors &amp; warnings (per record)</h2>"
            '<table><caption>Records that failed validation. Healthy rows above are unaffected.</caption>'
            "<thead><tr>"
            '<th scope="col">Ticket / Run</th><th scope="col">Source</th><th scope="col">Checkout</th>'
            '<th scope="col">Problem</th><th scope="col">Links</th>'
            "</tr></thead><tbody>%s</tbody></table>" % "".join(err_html)
        )

CSP = ("default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; script-src 'none'; "
       "connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none';")

STYLE = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
       margin: 2rem; color: #1a1a1a; background: #fafafa; }
h1 { font-size: 1.4rem; }
h2 { font-size: 1.1rem; margin-top: 2rem; border-bottom: 1px solid #ccc; padding-bottom: 0.25rem; }
table { border-collapse: collapse; width: 100%; margin-top: 0.75rem; background: #fff; }
caption { text-align: left; font-size: 0.85rem; color: #444; margin-bottom: 0.5rem; }
th, td { border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; vertical-align: top; font-size: 0.9rem; }
thead th { background: #eee; }
tbody th[scope="row"] { background: #f5f5f5; font-weight: 600; }
code { background: #eee; padding: 0.05rem 0.3rem; border-radius: 3px; }
.muted { color: #777; font-style: italic; }
.tag { background: #fde68a; color: #713f12; border-radius: 3px; padding: 0 0.3rem; font-size: 0.8rem; }
.warnings li, .empty { color: #92400e; }
a { color: #1d4ed8; }
"""

html_doc = (
    "<!DOCTYPE html>\n"
    '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    '<meta http-equiv="Content-Security-Policy" content="%s">\n'
    "<title>Nightshift Dashboard</title>\n<style>%s</style>\n</head>\n<body>\n%s\n</body>\n</html>\n"
) % (esc(CSP), STYLE, "\n".join(body_parts))

sys.stdout.write(html_doc)
NIGHTSHIFT_DASHBOARD_PY_EOF
