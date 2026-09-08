#!/usr/bin/env python3
"""Validate and record the small, typed behavioral-proof contract.

This module deliberately keeps provider execution out of the validator.  The
orchestrator supplies reviewed receipts; this process validates their shape
and the repository facts they claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

MAX_JSON = 1024 * 1024
TASK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RISKS = {"deterministic_logic", "prompt_behavior", "agent_behavior", "runtime_interaction", "safety_sensitive"}
KINDS = {"deterministic", "prototype", "not_applicable"}
PROFILE = "claude-subscription-text-v1"
DEFAULTS = {"version": 1, "development_calls": 8, "final_calls": 2, "repairs": 2,
            "infrastructure_failures": 2, "timeout_seconds": 120,
            "output_bytes": 1048576, "force_prompt": False}

class Invalid(Exception):
    pass

def fail(message, code=64):
    print(json.dumps({"status": "invalid" if code == 64 else "blocked", "reason": message}, separators=(",", ":")))
    return code

def pairs(text):
    def hook(items):
        out = {}
        for key, value in items:
            if key in out:
                raise Invalid("duplicate JSON key")
            out[key] = value
        return out
    return json.loads(text, object_pairs_hook=hook, parse_constant=lambda x: (_ for _ in ()).throw(Invalid("nonfinite JSON number")))

def read_json(path):
    p = Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size > MAX_JSON:
        raise Invalid("invalid JSON input")
    try:
        return pairs(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, Invalid) as exc:
        raise Invalid("invalid JSON input") from exc

def exact(obj, keys, label):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise Invalid("invalid " + label)

def identity(obj, label):
    exact(obj, {"provider", "author_id"}, label)
    if not all(isinstance(obj[k], str) and obj[k] for k in obj):
        raise Invalid("invalid " + label)

def digest(obj):
    value = json.loads(json.dumps(obj))
    def strip(x, top=False):
        if isinstance(x, dict):
            return {k: (None if (top and k == "review") or (not top and k == "review" and False) else strip(v)) for k, v in x.items()}
        if isinstance(x, list): return [strip(v) for v in x]
        return x
    value["applicability"]["review"] = None
    for case in value["cases"]:
        case["applicability"]["review"] = None
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()

def applicability(value, label):
    exact(value, {"kind", "rationale", "risks", "review"}, label)
    if value["kind"] not in KINDS or not isinstance(value["rationale"], str) or not value["rationale"]:
        raise Invalid("invalid " + label)
    if not isinstance(value["risks"], list) or len(set(value["risks"])) != len(value["risks"]):
        raise Invalid("invalid " + label)
    if any(r not in RISKS for r in value["risks"]): raise Invalid("invalid risk")
    if value["kind"] == "not_applicable" and value["risks"]:
        raise Invalid("not_applicable risks")
    review = value["review"]
    if review is not None:
        exact(review, {"reviewer_provider", "reviewer_author_id", "decision", "reviewed_input_sha256", "evidence_sha256"}, label + " review")
        if review["decision"] not in {"approve", "repair"} or not all(isinstance(review[x], str) for x in ("reviewer_provider", "reviewer_author_id")):
            raise Invalid("invalid review")
        for key in ("reviewed_input_sha256", "evidence_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", review[key]): raise Invalid("invalid digest")

def validate_doc(doc):
    exact(doc, {"version", "task", "ac_ids", "author", "applicability", "runtime", "prototype_files", "cases", "heldout"}, "scenario document")
    if doc["version"] != 1 or not isinstance(doc["task"], str) or not TASK_RE.fullmatch(doc["task"]): raise Invalid("invalid task")
    if not isinstance(doc["ac_ids"], list) or not doc["ac_ids"] or len(set(doc["ac_ids"])) != len(doc["ac_ids"]): raise Invalid("invalid ac_ids")
    if not all(isinstance(x, str) and x for x in doc["ac_ids"]): raise Invalid("invalid ac_ids")
    identity(doc["author"], "author"); applicability(doc["applicability"], "applicability")
    if not isinstance(doc["prototype_files"], list) or any(not isinstance(x, str) or not x or Path(x).is_absolute() or ".." in Path(x).parts for x in doc["prototype_files"]): raise Invalid("invalid prototype_files")
    if doc["runtime"] is not None:
        exact(doc["runtime"], {"profile", "model", "cli_version", "system_prompt_file"}, "runtime")
        if doc["runtime"]["profile"] != PROFILE: raise Invalid("unsupported runtime profile")
    if not isinstance(doc["cases"], list) or len({c.get("id") for c in doc["cases"] if isinstance(c, dict)}) != len(doc["cases"]): raise Invalid("duplicate case id")
    required = {"id", "ac_ids", "required", "applicability", "given", "when", "then", "forbidden", "input", "expected", "prohibited", "counterexamples", "visibility"}
    covered = set(); kinds = set(); risks = set()
    for c in doc["cases"]:
        exact(c, required, "case")
        if not isinstance(c["id"], str) or not c["id"] or c["visibility"] not in {"public", "held_out"}: raise Invalid("invalid case")
        if not isinstance(c["ac_ids"], list) or not c["ac_ids"] or any(x not in doc["ac_ids"] for x in c["ac_ids"]): raise Invalid("invalid case ac_ids")
        if not isinstance(c["required"], bool): raise Invalid("invalid required")
        applicability(c["applicability"], "case applicability"); covered.update(c["ac_ids"] if c["required"] else [])
        kinds.add(c["applicability"]["kind"]); risks.update(c["applicability"]["risks"])
        if c["applicability"]["kind"] == "prototype" and (not isinstance(c["input"], str) or not c["input"] or not c["expected"]): raise Invalid("prototype requires input and expected oracle")
    if covered != set(doc["ac_ids"]): raise Invalid("required AC coverage missing")
    if "prompt_behavior" in risks or "agent_behavior" in risks or "runtime_interaction" in risks:
        if "prototype" not in kinds: raise Invalid("risk downgraded without prototype")
    derived = "prototype" if "prototype" in kinds else ("deterministic" if "deterministic" in kinds else "not_applicable")
    if doc["applicability"]["kind"] != derived or set(doc["applicability"]["risks"]) != risks: raise Invalid("applicability summary mismatch")
    return doc

def config(project):
    path = Path(project) / ".nightshift.toml"
    if not path.exists(): path = Path(project) / "nightshift.toml"
    values = dict(DEFAULTS)
    if path.exists():
        try:
            import tomllib
            with path.open("rb") as f: parsed = tomllib.load(f)
            section = parsed.get("behavior_proof", {})
            if not isinstance(section, dict) or set(section) - set(DEFAULTS): raise Invalid("invalid behavior_proof keys")
            values.update(section)
        except (OSError, tomllib.TOMLDecodeError, Invalid): raise Invalid("invalid behavior_proof configuration")
    if values["version"] != 1 or not isinstance(values["version"], int) or isinstance(values["version"], bool): raise Invalid("invalid behavior_proof version")
    bounds = {"development_calls": (1,64), "final_calls":(1,64), "repairs":(0,2), "infrastructure_failures":(0,2), "timeout_seconds":(1,120), "output_bytes":(1,1048576)}
    for key,(lo,hi) in bounds.items():
        if not isinstance(values[key], int) or isinstance(values[key], bool) or not lo <= values[key] <= hi: raise Invalid("invalid behavior_proof value")
    if not isinstance(values["force_prompt"], bool): raise Invalid("invalid force_prompt")
    return values

def state_path(project, task):
    common = subprocess_common(project)
    return common / "nightshift" / "behavior-proof" / task / "state.json"

def subprocess_common(project):
    import subprocess
    try:
        value = subprocess.check_output(["git", "-C", str(project), "rev-parse", "--git-common-dir"], text=True, stderr=subprocess.DEVNULL).strip()
        p = Path(value); return (Path(project) / p).resolve() if not p.is_absolute() else p.resolve()
    except Exception as exc:
        raise Invalid("non-Git project cannot establish proof identity") from exc

def write_state(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as f:
        json.dump(value, f, sort_keys=True, separators=(",", ":")); f.write("\n"); tmp=f.name
    os.replace(tmp, path)

def main():
    p = argparse.ArgumentParser(add_help=True); p.add_argument("operation", choices=["validate","seal","gate","status","expose","record-red","record-final","run","challenge"]); p.add_argument("--project", required=True); p.add_argument("--task"); p.add_argument("--scenarios"); p.add_argument("--config-only", action="store_true"); p.add_argument("--gate", choices=["development","final"]); p.add_argument("--out"); p.add_argument("--evidence"); p.add_argument("--case")
    try:
        a=p.parse_args(); project=Path(a.project).resolve(); cfg=config(project)
        if a.config_only:
            if a.operation != "validate": raise Invalid("config-only requires validate")
            print(json.dumps({"status":"valid","config":cfg}, separators=(",",":"))); return 0
        if not a.task or not TASK_RE.fullmatch(a.task): raise Invalid("invalid task")
        if a.operation == "validate":
            if not a.scenarios: raise Invalid("scenarios required")
            validate_doc(read_json(a.scenarios)); print(json.dumps({"status":"valid","task":a.task},separators=(",",":"))); return 0
        sp = state_path(project, a.task)
        if a.operation == "seal":
            if not a.scenarios: raise Invalid("scenarios required")
            doc=validate_doc(read_json(a.scenarios)); record={"version":1,"task":a.task,"scenario_sha256":hashlib.sha256(Path(a.scenarios).read_bytes()).hexdigest(),"applicability":doc["applicability"],"config":cfg,"development":{"red":None,"final":None},"created":True}
            write_state(sp, record); print(json.dumps({"status":"sealed","task":a.task},separators=(",",":"))); return 0
        if a.operation in {"record-red","record-final"}:
            if not a.evidence: raise Invalid("evidence required")
            evidence=read_json(a.evidence); exact(evidence,{"version","task","gate","observer","scenario_ids","command","exit_code","assertions","log","tests","red_lock_sha","source_hashes"},"evidence")
            if evidence["task"] != a.task or evidence["gate"] != ("development" if a.operation == "record-red" else "final"): raise Invalid("evidence task or gate mismatch")
            if not isinstance(evidence["scenario_ids"],list) or not evidence["scenario_ids"]: raise Invalid("invalid evidence coverage")
            if not isinstance(evidence["exit_code"],int) or isinstance(evidence["exit_code"],bool): raise Invalid("invalid evidence exit")
            if a.operation == "record-red" and not (1 <= evidence["exit_code"] <= 255): raise Invalid("RED requires nonzero exit")
            if a.operation == "record-final" and evidence["exit_code"] != 0: raise Invalid("final requires zero exit")
            if not sp.exists(): raise Invalid("proof is not sealed")
            record=json.loads(sp.read_text()); record["development" if a.operation == "record-red" else "final"]["red" if a.operation == "record-red" else "final"]=evidence
            write_state(sp,record); print(json.dumps({"status":"recorded","task":a.task,"gate":evidence["gate"]},separators=(",",":"))); return 0
        if a.operation in {"gate","status"}:
            if not sp.exists(): return fail("proof state unavailable",1)
            record=json.loads(sp.read_text()); ready=bool(record["development"]["red"] and record["final"]["final"])
            print(json.dumps({"status":"pass" if ready else "blocked","task":a.task,"reason":"proof complete" if ready else "proof evidence incomplete"},separators=(",",":"))); return 0 if ready else 1
        raise Invalid("operation not yet available")
    except Invalid as e: return fail(str(e),64)
    except (OSError, ValueError, TypeError) as e: return fail("proof operation failed",1)
if __name__ == "__main__": sys.exit(main())
