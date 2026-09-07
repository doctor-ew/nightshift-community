#!/usr/bin/env bash
make_repo() {
  mkdir -p "$1"
  git -C "$1" init -q -b main
  git -C "$1" config user.name 'Nightshift fixture'
  git -C "$1" config user.email 'nightshift-bot@local'
  printf '.nightshift/\n' > "$1/.gitignore"
  printf 'base\n' > "$1/source.txt"
  git -C "$1" add .gitignore source.txt
  git -C "$1" commit -qm base
}
make_spec() {
  mkdir -p "$1/docs/$2"
  printf '# fixture\n\n## Files to Change\n\n| File | Action |\n|---|---|\n| `source.txt` | MODIFY |\n\n## Acceptance Criteria\n1. fixture\n' > "$1/docs/$2/SPEC.md"
}
