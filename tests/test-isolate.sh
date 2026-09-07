#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; ISOLATE="$ROOT/scripts/nightshift-isolate.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nightshift-isolate.XXXXXX")"; trap 'rm -rf "$TMP_ROOT"' EXIT
mkdir -p "$TMP_ROOT/assigned"
WORKTREE="$(cd "$TMP_ROOT/assigned" && pwd -P)"
PLAN=$("$ISOLATE" render --runtime docker --worktree "$WORKTREE" --image worker:latest --network none -- bash -lc 'echo ok')
printf '%s' "$PLAN" | jq -e --arg worktree "$WORKTREE" '.disposable and .network == "none" and .worktree == $worktree and ([.args[] | select(contains("src=" + $worktree))] | length) == 1' >/dev/null
if "$ISOLATE" render --worktree "$TMP_ROOT/assigned" --image worker:latest --network host -- true >/dev/null 2>&1; then echo 'FAIL: host network was accepted' >&2; exit 1; fi
mkdir -p "$TMP_ROOT/bin"
printf '%s\n' '#!/usr/bin/env bash' 'set -eu' 'log="$(dirname "$0")/calls"' 'printf "%s\n" "$*" >> "$log"' '[ -z "${UNRELATED_SECRET:-}" ] || exit 91' 'if [[ "$*" == *"version --format"* ]]; then echo 28.1.0; fi' 'if [[ "$*" == *"inspect "* ]]; then net=$(sed -n "s/^network create --internal .* //p" "$log" | tail -1); printf "[{\"NetworkSettings\":{\"Networks\":{\"%s\":{\"IPAddress\":\"172.28.0.2\"}}}}]\\n" "$net"; fi' 'if [[ "$*" == *"--env TEST_SECRET"* ]]; then [ "${TEST_SECRET:-}" = shh ]; fi' > "$TMP_ROOT/bin/docker"
chmod +x "$TMP_ROOT/bin/docker"
cp "$TMP_ROOT/bin/docker" "$TMP_ROOT/bin/podman"
printf '%s\n' '{"profiles":{"test":{"credential_names":["TEST_SECRET"],"egress_allowlist":[]},"online":{"credential_names":["TEST_SECRET"],"egress_allowlist":["github.com"]}}}' > "$TMP_ROOT/profiles.json"
for RUNTIME in docker podman rancher; do
  PATH="$TMP_ROOT/bin:$PATH" TEST_SECRET=shh UNRELATED_SECRET=hidden "$ISOLATE" run --runtime "$RUNTIME" --worktree "$WORKTREE" --image worker:latest --profile test --profiles "$TMP_ROOT/profiles.json" -- true
done
grep -Fq -- '--context rancher-desktop run' "$TMP_ROOT/bin/calls"
grep -Fq -- '--network none' "$TMP_ROOT/bin/calls"
if grep -Eq 'shh|hidden' "$TMP_ROOT/bin/calls"; then echo 'FAIL: secret in args' >&2; exit 1; fi
if PATH="$TMP_ROOT/bin:$PATH" "$ISOLATE" run --runtime docker --worktree "$WORKTREE" --image worker:latest --profile test --profiles "$TMP_ROOT/profiles.json" -- true >/dev/null 2>&1; then echo 'FAIL: missing secret accepted' >&2; exit 1; fi
PATH="$TMP_ROOT/bin:$PATH" TEST_SECRET=shh NIGHTSHIFT_PROXY_IMAGE=squid:test "$ISOLATE" run --runtime docker --worktree "$WORKTREE" --image worker:latest --profile online --profiles "$TMP_ROOT/profiles.json" -- true
if PATH="$TMP_ROOT/bin:$PATH" TEST_SECRET=shh NIGHTSHIFT_PROXY_IMAGE= "$ISOLATE" run --runtime docker --worktree "$WORKTREE" --image worker:latest --profile online --profiles "$TMP_ROOT/profiles.json" -- true >/dev/null 2>&1; then echo 'FAIL: missing proxy accepted' >&2; exit 1; fi
if PATH="$TMP_ROOT/bin:$PATH" TEST_SECRET=shh NIGHTSHIFT_PROXY_IMAGE=squid:test "$ISOLATE" run --runtime podman --worktree "$WORKTREE" --image worker:latest --profile online --profiles "$TMP_ROOT/profiles.json" -- true >/dev/null 2>&1; then echo 'FAIL: unenforced Podman egress accepted' >&2; exit 1; fi
sed 's/echo 28.1.0/echo 27.5.0/' "$TMP_ROOT/bin/docker" > "$TMP_ROOT/bin/old-docker"
mv "$TMP_ROOT/bin/old-docker" "$TMP_ROOT/bin/docker"
chmod +x "$TMP_ROOT/bin/docker"
if PATH="$TMP_ROOT/bin:$PATH" TEST_SECRET=shh NIGHTSHIFT_PROXY_IMAGE=squid:test "$ISOLATE" run --runtime docker --worktree "$WORKTREE" --image worker:latest --profile online --profiles "$TMP_ROOT/profiles.json" -- true >/dev/null 2>&1; then echo 'FAIL: old Docker egress accepted' >&2; exit 1; fi
grep -Fq -- 'network create --internal' "$TMP_ROOT/bin/calls"
grep -Fq -- '--dns 172.28.0.2' "$TMP_ROOT/bin/calls"
grep -Fq -- 'HTTPS_PROXY=http://172.28.0.2:3128' "$TMP_ROOT/bin/calls"
grep -Fq -- 'network rm nightshift-egress-' "$TMP_ROOT/bin/calls"
printf 'PASS: disposable workers, runtime adapters, secret injection, proxy topology\n'
