#!/usr/bin/env bash
# Inspect selected failure/adoption evidence; never execute the referenced mechanisms.
set -euo pipefail
exec python3 - "$@" <<'PY'
import datetime
import hashlib
import json
import math
import os
import re
import stat
import sys


class Invalid(Exception):
    pass


def require(condition):
    if not condition:
        raise Invalid()


def integer(value):
    return type(value) is int


def timestamp(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value))
    return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result)
        result[key] = value
    return result


def nonfinite(_):
    raise Invalid()


def finite_float(value):
    number = float(value)
    require(math.isfinite(number))
    return number


def parse(data):
    return json.loads(data, object_pairs_hook=pairs, parse_constant=nonfinite, parse_float=finite_float)


def packed(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(packed(value).encode("utf-8")).hexdigest()


def read_file(project, relative):
    require(isinstance(relative, str) and relative and not os.path.isabs(relative))
    require(".." not in relative.split(os.sep) and "\x00" not in relative)
    path = os.path.realpath(os.path.join(project, relative))
    require(os.path.commonpath([project, path]) == project)
    metadata = os.stat(path)
    require(stat.S_ISREG(metadata.st_mode) and metadata.st_size > 0)
    # A descriptor check avoids accidentally consuming a nonregular replacement.
    with open(path, "rb") as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode))
        data = stream.read()
    require(data)
    return data


CATEGORIES = {
    "continue to the next gate": "continue",
    "inspect the final gate output and repair the smallest in-scope cause": "inspect-and-repair",
    "Configure NIGHTSHIFT_WORKER_IMAGE; host execution is disabled.": "configure-isolation",
}
KINDS = {"test", "guardrail", "fixture", "manifest", "prompt"}
HEX = re.compile(r"[0-9a-f]{64}\Z")


def receipts_from(data):
    records = {}
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            continue
        row = parse(line)
        require(isinstance(row, dict))
        require(isinstance(row.get("ticket"), str) and row["ticket"].strip())
        timestamp(row.get("generated_at"))
        gate, provider, status = row.get("gate"), row.get("provider"), row.get("status")
        require(isinstance(gate, str) and gate in {"implement", "review", "drift", "qa"})
        require(isinstance(provider, str) and provider in {"codex", "claude", "local"})
        require(isinstance(status, str) and status in {"complete", "failed", "blocked", "needs-decision"})
        require(isinstance(row.get("attempts"), list) and isinstance(row.get("next_action"), str))
        exit_code = None
        for attempt in row["attempts"]:
            require(isinstance(attempt, dict))
            keys = [key for key in ("attempt", "repair_after_attempt") if key in attempt]
            require(len(keys) == 1)
            index = attempt[keys[0]]
            code = attempt.get("exit_code")
            require(integer(index) and index > 0 and integer(code) and 0 <= code <= 255)
            if keys[0] == "attempt":
                exit_code = code
        if status == "complete":
            require(exit_code == 0)
        elif status in {"failed", "needs-decision"}:
            require(exit_code is not None and exit_code != 0)
        identity = digest({key: row[key] for key in ("ticket", "generated_at", "gate", "provider")})
        structural = {"gate": gate, "provider": provider, "status": status,
                      "exit_code": exit_code, "next_action_category": CATEGORIES.get(row["next_action"], "other")}
        record = dict(structural, evidence_id=identity, generated_at=row["generated_at"],
                      signature=digest(structural) if status != "complete" else None)
        require(identity not in records or records[identity] == record)
        records[identity] = record
    require(records)
    return records


def registry_from(data):
    root = parse(data)
    require(isinstance(root, dict) and integer(root.get("schema_version")) and root["schema_version"] == 1)
    require(isinstance(root.get("learnings"), list))
    ids = set()
    for entry in root["learnings"]:
        require(isinstance(entry, dict))
        key = entry.get("id")
        require(isinstance(key, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", key))
        require(key not in ids)
        ids.add(key)
        require(isinstance(entry.get("signature"), str) and HEX.fullmatch(entry["signature"]))
        timestamp(entry.get("adopted_at"))
        require(isinstance(entry.get("kind"), str) and entry["kind"] in KINDS)
        for field in ("mechanism", "validation"):
            require(field not in entry or isinstance(entry[field], str))
        if "evidence" in entry:
            require(isinstance(entry["evidence"], list) and all(isinstance(item, str) for item in entry["evidence"]))
    return sorted(root["learnings"], key=lambda entry: entry["id"])


def cohort(records, signature):
    count = len(records)
    completed = sum(record["status"] == "complete" for record in records)
    recurring = sum(record["signature"] == signature for record in records)
    return {"total_runs": count, "completed_runs": completed, "recurrences": recurring,
            "completion_rate": completed / count if count else None,
            "recurrence_rate": recurring / count if count else None}


def learning_result(entry, project, records, clusters):
    signature = entry["signature"]
    evidence = entry.get("evidence", [])
    # Invalid references never appear as arbitrary text in the report.
    safe_evidence = sorted(set(value for value in evidence if HEX.fullmatch(value)))
    result = {"id": entry["id"], "signature": signature, "status": "unsupported", "reasons": [],
              "evidence": safe_evidence, "outcomes": {"status": "unknown"}}

    def unsupported(reason):
        result["reasons"] = [reason]
        return result

    if entry["kind"] == "prompt":
        return unsupported("prompt_only")
    if not entry.get("mechanism"):
        return unsupported("missing_mechanism")
    if not evidence:
        return unsupported("missing_evidence")
    if not entry.get("validation"):
        return unsupported("missing_validation")
    if len(evidence) != len(set(evidence)):
        return unsupported("duplicate_evidence")
    if signature not in clusters or len(evidence) < 2:
        return unsupported("insufficient_evidence")
    if any(value not in records for value in evidence):
        return unsupported("unknown_evidence")
    selected = [records[value] for value in evidence]
    if any(row["signature"] != signature for row in selected):
        return unsupported("evidence_signature_mismatch")
    if any(row["generated_at"] >= entry["adopted_at"] for row in selected):
        return unsupported("evidence_not_prior")
    try:
        mechanism = read_file(project, entry["mechanism"])
    except Exception:
        return unsupported("invalid_mechanism")
    mechanism_hash = hashlib.sha256(mechanism).hexdigest()
    try:
        validation = parse(read_file(project, entry["validation"]))
        require(isinstance(validation, dict))
        require(integer(validation.get("schema_version")) and validation["schema_version"] == 1)
        require(validation.get("status") == "passed")
        require(validation.get("mechanism") == entry["mechanism"])
        require(validation.get("sha256") == mechanism_hash)
        verified_evidence = validation.get("evidence")
        require(isinstance(verified_evidence, list) and all(isinstance(v, str) for v in verified_evidence))
        require(len(verified_evidence) == len(set(verified_evidence)) and set(verified_evidence) == set(evidence))
        timestamp(validation.get("validated_at"))
        require(max(row["generated_at"] for row in selected) <= validation["validated_at"] <= entry["adopted_at"])
    except Exception:
        return unsupported("invalid_validation")
    target = clusters[signature]
    comparable = [record for record in records.values()
                  if record["gate"] == target["gate"] and record["provider"] == target["provider"]]
    before = cohort([row for row in comparable if row["generated_at"] < entry["adopted_at"]], signature)
    after = cohort([row for row in comparable if row["generated_at"] > entry["adopted_at"]], signature)
    if not before["total_runs"] or not after["total_runs"]:
        outcome = "insufficient_evidence"
    else:
        # Integer cross-products avoid rounding affecting the classification.
        left = after["completed_runs"] * before["total_runs"]
        right = before["completed_runs"] * after["total_runs"]
        outcome = "improved" if left > right else "regressed" if left < right else "unchanged"
    result.update(status="supported", mechanism={"kind": entry["kind"], "path": entry["mechanism"], "sha256": mechanism_hash},
                  outcomes={"status": outcome, "before": before, "after": after})
    return result


def main():
    arguments = sys.argv[1:]
    require(len(arguments) == 6)
    options = {}
    for index in range(0, len(arguments), 2):
        option, value = arguments[index:index + 2]
        require(option in {"--project", "--receipts", "--learnings"} and option not in options and value)
        options[option] = value
    require(len(options) == 3)
    project = os.path.realpath(options["--project"])
    require(os.path.isdir(project))
    records = receipts_from(read_file(project, options["--receipts"]))
    learnings = registry_from(read_file(project, options["--learnings"]))
    clusters = {}
    for record in records.values():
        signature = record["signature"]
        if signature is None:
            continue
        if signature not in clusters:
            clusters[signature] = {key: record[key] for key in
                                   ("gate", "provider", "status", "exit_code", "next_action_category", "signature")}
            clusters[signature]["evidence_ids"] = []
        clusters[signature]["evidence_ids"].append(record["evidence_id"])
    for cluster in clusters.values():
        cluster["evidence_ids"].sort()
        cluster["count"] = len(cluster["evidence_ids"])
        cluster["repeated"] = cluster["count"] >= 2
    report = {"schema_version": 1, "receipt_count": len(records),
              "clusters": [clusters[key] for key in sorted(clusters)],
              "learnings": [learning_result(entry, project, records, clusters) for entry in learnings]}
    return packed(report)


try:
    output = main()
except Exception:
    sys.stderr.write("nightshift-failure-memory: invalid input\n")
    sys.exit(1)
sys.stdout.write(output + "\n")
PY
