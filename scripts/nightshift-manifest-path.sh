#!/usr/bin/env bash
set -euo pipefail
PROJECT="${PWD}"
if [ "${1:-}" = --project ]; then PROJECT="${2:?directory required}"; shift 2; fi
[ "$#" -eq 0 ] || exit 64
if [ -e "$PROJECT/.nightshift.toml" ]; then
  printf '%s\n' "$PROJECT/.nightshift.toml"
else
  printf '%s\n' "$PROJECT/nightshift.toml"
fi
