#!/usr/bin/env python3
"""Normalize allowlisted usage observations from Claude or Codex JSON output.

The owning runtime boundary remains responsible for trusted run, invocation,
ticket, role, and selected-model identity. This helper parses data only; it
never executes captured output or derives trusted attribution from it.
"""

import argparse
import json
import math
import sys
from pathlib import Path


SCHEMA_VERSION = 2
NORMALIZER_VERSION = 1
TOKEN_CATEGORIES = (
    "fresh_input",
    "cache_read_input",
    "cache_write_input",
    "output",
)


class UsageInputError(Exception):
    """The captured provider output is not readable JSON or JSONL."""


def _quality():
    return {"category_missing_count": 0, "conflict_count": 0}


def _merge_quality(target, source):
    target["category_missing_count"] += source["category_missing_count"]
    target["conflict_count"] += source["conflict_count"]


def _nonnegative_integer(mapping, key, quality):
    if key not in mapping or mapping[key] is None:
        quality["category_missing_count"] += 1
        return None
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        quality["conflict_count"] += 1
        return None
    return value


def _optional_usd(mapping, key, quality):
    if key not in mapping or mapping[key] is None:
        return None
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        quality["conflict_count"] += 1
        return None
    value = float(value)
    if value < 0 or not math.isfinite(value):
        quality["conflict_count"] += 1
        return None
    return value


def _normalized_usage(fresh, cache_read, cache_write, output, reasoning=None):
    values = (fresh, cache_read, cache_write, output)
    total = sum(values) if all(value is not None for value in values) else None
    return {
        "fresh_input": fresh,
        "cache_read_input": cache_read,
        "cache_write_input": cache_write,
        "output": output,
        "reasoning_output": reasoning,
        "total": total,
    }


def _claude_usage(raw, quality):
    if not isinstance(raw, dict):
        quality["category_missing_count"] += len(TOKEN_CATEGORIES)
        return _normalized_usage(None, None, None, None)
    return _normalized_usage(
        _nonnegative_integer(raw, "input_tokens", quality),
        _nonnegative_integer(raw, "cache_read_input_tokens", quality),
        _nonnegative_integer(raw, "cache_creation_input_tokens", quality),
        _nonnegative_integer(raw, "output_tokens", quality),
    )


def _claude_model_usage(raw, quality):
    if not isinstance(raw, dict):
        quality["category_missing_count"] += len(TOKEN_CATEGORIES)
        return _normalized_usage(None, None, None, None), [], None, None

    field_names = {
        "fresh_input": "inputTokens",
        "cache_read_input": "cacheReadInputTokens",
        "cache_write_input": "cacheCreationInputTokens",
        "output": "outputTokens",
    }
    normalized_models = []
    model_costs = []

    for model_name in sorted(raw):
        model_raw = raw[model_name]
        model_quality = _quality()
        if not isinstance(model_raw, dict):
            model_quality["category_missing_count"] += len(TOKEN_CATEGORIES)
            model_raw = {}
        values = {
            category: _nonnegative_integer(model_raw, provider_key, model_quality)
            for category, provider_key in field_names.items()
        }
        model_cost = _optional_usd(model_raw, "costUSD", model_quality)
        normalized_models.append({
            "reported_model": model_name,
            "usage": _normalized_usage(
                values["fresh_input"],
                values["cache_read_input"],
                values["cache_write_input"],
                values["output"],
            ),
            "provider_reported_estimate_usd": model_cost,
        })
        model_costs.append(model_cost)
        _merge_quality(quality, model_quality)

    aggregates = {}
    for category in TOKEN_CATEGORIES:
        values = [item["usage"][category] for item in normalized_models]
        aggregates[category] = (
            sum(values) if values and all(value is not None for value in values) else None
        )

    usage = _normalized_usage(
        aggregates["fresh_input"],
        aggregates["cache_read_input"],
        aggregates["cache_write_input"],
        aggregates["output"],
    )
    reported_model = (
        normalized_models[0]["reported_model"] if len(normalized_models) == 1 else None
    )
    aggregate_cost = (
        sum(model_costs)
        if model_costs and all(value is not None for value in model_costs)
        else None
    )
    return usage, normalized_models, reported_model, aggregate_cost


def _provider_cost(estimate, provider, source):
    pricing_sources = []
    if estimate is not None:
        pricing_sources.append({
            "kind": "provider_reported_estimate",
            "provider": provider,
            "source": source,
            "runtime_version": None,
            "normalizer_version": NORMALIZER_VERSION,
        })
    return {
        "provider_reported_estimate_usd": estimate,
        "token_derived_estimate_usd": None,
        "actual_billed_usd": None,
        "pricing_sources": pricing_sources,
    }


def _claude_status(event):
    subtype = event.get("subtype")
    if event.get("is_error") is True:
        return "failed"
    if subtype == "success" or event.get("is_error") is False:
        return "success"
    return "failed"


def _claude_observation(event, sequence):
    main_quality = _quality()
    main_usage = _claude_usage(event.get("usage"), main_quality)
    selected_quality = _quality()

    raw_model_usage = event.get("modelUsage")
    has_model_usage = isinstance(raw_model_usage, dict) and bool(raw_model_usage)
    if has_model_usage:
        usage, model_usage, reported_model, model_cost = _claude_model_usage(
            raw_model_usage, selected_quality
        )
        coverage_scope = "inclusive"
        selected_source = "result.modelUsage"
        nonadditive_usage = main_usage
    else:
        usage = main_usage
        model_usage = None
        reported_model = None
        model_cost = None
        coverage_scope = "self"
        selected_source = "result.usage"
        nonadditive_usage = None
        _merge_quality(selected_quality, main_quality)

    total_cost = _optional_usd(event, "total_cost_usd", selected_quality)
    if total_cost is not None:
        estimate = total_cost
        cost_source = "result.total_cost_usd"
    else:
        estimate = model_cost
        cost_source = "result.modelUsage.costUSD"

    return {
        "schema_version": SCHEMA_VERSION,
        "provider": "claude",
        "sequence": sequence,
        "stream_epoch": 0,
        "status": _claude_status(event),
        "provider_status": event.get("subtype") if isinstance(event.get("subtype"), str) else None,
        "reported_model": reported_model,
        "coverage_scope": coverage_scope,
        "parent_invocation_id": None,
        "included_invocation_ids": None,
        "child_kind": "none",
        "usage": usage,
        "nonadditive_usage": nonadditive_usage,
        "cost": _provider_cost(estimate, "claude", cost_source),
        "completeness": selected_quality,
        "provenance": {
            "source_event": "result",
            "source_version": NORMALIZER_VERSION,
            "runtime_version": None,
            "selected_usage_source": selected_source,
            "main_loop_usage": main_usage,
            "main_loop_quality": main_quality,
            "model_usage": model_usage,
            "total_cost_usd": total_cost,
            "model_usage_cost_usd": model_cost,
            "final_coverage_missing": False,
        },
    }


def _usage_vector(observation):
    usage = observation["usage"]
    values = [usage[category] for category in TOKEN_CATEGORIES]
    estimate = observation["cost"]["provider_reported_estimate_usd"]
    if estimate is not None:
        values.append(estimate)
    return values


def _counter_reset(previous, current):
    previous_values = _usage_vector(previous)
    current_values = _usage_vector(current)
    for old, new in zip(previous_values, current_values):
        if old is not None and new is not None and new < old:
            return True
    return False


def _zeroed_execution_error(previous, current):
    if current["provider_status"] != "error_during_execution":
        return False
    current_tokens = [current["usage"][key] for key in TOKEN_CATEGORIES]
    previous_tokens = [previous["usage"][key] for key in TOKEN_CATEGORIES]
    return (
        all(value == 0 for value in current_tokens)
        and any(value is not None and value > 0 for value in previous_tokens)
    )


def _mark_missing_final_coverage(observation):
    observation["usage"] = _normalized_usage(None, None, None, None)
    observation["cost"] = _provider_cost(None, "claude", "result.total_cost_usd")
    observation["completeness"]["category_missing_count"] += len(TOKEN_CATEGORIES)
    observation["provenance"]["final_coverage_missing"] = True


def _normalize_claude(events):
    results = [event for event in events if event.get("type") == "result"]
    retained = []
    epoch = 0

    for sequence, event in enumerate(results):
        current = _claude_observation(event, sequence)
        current["stream_epoch"] = epoch
        if not retained:
            retained.append(current)
            continue

        previous = retained[-1]
        if _zeroed_execution_error(previous, current):
            epoch += 1
            current["stream_epoch"] = epoch
            _mark_missing_final_coverage(current)
            retained.append(current)
        elif _counter_reset(previous, current):
            epoch += 1
            current["stream_epoch"] = epoch
            retained.append(current)
        else:
            current["stream_epoch"] = previous["stream_epoch"]
            retained[-1] = current
    return retained


def _normalize_codex_usage(raw, quality):
    if not isinstance(raw, dict):
        quality["category_missing_count"] += 5
        return _normalized_usage(None, None, None, None, None)

    provider_input = _nonnegative_integer(raw, "input_tokens", quality)
    cache_read = _nonnegative_integer(raw, "cached_input_tokens", quality)
    cache_write = _nonnegative_integer(raw, "cache_write_input_tokens", quality)
    output = _nonnegative_integer(raw, "output_tokens", quality)
    reasoning = _nonnegative_integer(raw, "reasoning_output_tokens", quality)

    fresh = None
    if provider_input is not None and cache_read is not None and cache_write is not None:
        if cache_read + cache_write > provider_input:
            quality["conflict_count"] += 1
        else:
            fresh = provider_input - cache_read - cache_write

    if reasoning is not None and output is not None and reasoning > output:
        quality["conflict_count"] += 1
        reasoning = None

    usage = _normalized_usage(fresh, cache_read, cache_write, output, reasoning)
    usage["total"] = (
        provider_input + output
        if provider_input is not None and output is not None
        else None
    )
    return usage


def _normalize_codex(events):
    observations = []
    completed = [event for event in events if event.get("type") == "turn.completed"]
    for sequence, event in enumerate(completed):
        quality = _quality()
        usage = _normalize_codex_usage(event.get("usage"), quality)
        observations.append({
            "schema_version": SCHEMA_VERSION,
            "provider": "codex",
            "sequence": sequence,
            "stream_epoch": sequence,
            "status": "success",
            "provider_status": "turn.completed",
            "reported_model": None,
            "coverage_scope": "self",
            "parent_invocation_id": None,
            "included_invocation_ids": None,
            "child_kind": "none",
            "usage": usage,
            "nonadditive_usage": None,
            "cost": _provider_cost(None, "codex", "turn.completed.usage"),
            "completeness": quality,
            "provenance": {
                "source_event": "turn.completed",
                "source_version": NORMALIZER_VERSION,
                "runtime_version": None,
                "provider_input_tokens": (
                    event["usage"].get("input_tokens")
                    if isinstance(event.get("usage"), dict)
                    and isinstance(event["usage"].get("input_tokens"), int)
                    and not isinstance(event["usage"].get("input_tokens"), bool)
                    and event["usage"].get("input_tokens") >= 0
                    else None
                ),
            },
        })
    return observations


def _read_events(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise UsageInputError("input_unavailable") from error

    if not text.strip():
        return []

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        events = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise UsageInputError(f"invalid_json_line:{line_number}") from error
            if not isinstance(value, dict):
                raise UsageInputError(f"invalid_event_line:{line_number}")
            events.append(value)
        return events

    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    raise UsageInputError("invalid_json_document")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Normalize allowlisted Claude or Codex usage observations."
    )
    parser.add_argument("--provider", required=True, choices=("claude", "codex"))
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)

    try:
        events = _read_events(args.input)
    except UsageInputError as error:
        print(
            json.dumps({
                "schema_version": SCHEMA_VERSION,
                "provider": args.provider,
                "observations": [],
                "available": False,
                "error": str(error),
            }, sort_keys=True)
        )
        return 0

    if args.provider == "claude":
        observations = _normalize_claude(events)
    else:
        observations = _normalize_codex(events)
    print(json.dumps(observations, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
