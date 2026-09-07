#!/usr/bin/env bash
# Disposable workers; optional domain-gated HTTPS uses an isolated proxy.
set -euo pipefail
usage() { echo 'usage: nightshift-isolate.sh render|run --worktree DIR --image IMAGE [--runtime auto|docker|podman|rancher] [--profile NAME --profiles FILE --policy-log FILE] -- COMMAND...' >&2; exit 64; }
MODE="${1:-}"; shift || true
case "$MODE" in render|run) ;; *) usage;; esac
WORKTREE=""; IMAGE="${NIGHTSHIFT_WORKER_IMAGE:-}"; RUNTIME="${NIGHTSHIFT_CONTAINER_RUNTIME:-auto}"; NETWORK=none
PROFILE="${NIGHTSHIFT_CREDENTIAL_PROFILE:-offline}"; PROFILES="${NIGHTSHIFT_PROFILES_FILE:-}"; POLICY_LOG=""; TOKEN=""; AT=""
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
while [ "$#" -gt 0 ]; do
  [ "$1" != -- ] || { shift; break; }
  [ "$#" -ge 2 ] || usage
  case "$1" in
    --worktree) WORKTREE="$2";; --image) IMAGE="$2";; --runtime) RUNTIME="$2";; --network) NETWORK="$2";;
    --profile) PROFILE="$2";; --profiles) PROFILES="$2";; --policy-log) POLICY_LOG="$2";;
    --confirmation-token) TOKEN="$2";; --confirmed-at) AT="$2";; *) usage;;
  esac
  shift 2
done
[ -n "$IMAGE" ] && [ -d "$WORKTREE" ] && [ "$#" -gt 0 ] || usage
[ "$NETWORK" = none ] || { echo 'direct networking prohibited; configure an egress profile' >&2; exit 78; }
WORKTREE="$(cd "$WORKTREE" && pwd -P)"
case "$WORKTREE" in /|*,*) echo 'unsafe worktree mount path' >&2; exit 78;; esac
PLAN=$(bash "$SCRIPT_DIR/nightshift-credentials.sh" plan --profile "$PROFILE" --profiles "$PROFILES" --worktree "$WORKTREE" --policy-log "$POLICY_LOG" --confirmation-token "$TOKEN" --confirmed-at "$AT")
case "$RUNTIME" in
  auto) if command -v docker >/dev/null 2>&1; then RUNTIME=docker; elif command -v podman >/dev/null 2>&1; then RUNTIME=podman; else echo 'container runtime required; no host fallback' >&2; exit 69; fi;;
  docker|podman|rancher) ;; *) usage;;
esac
ENGINE=("$RUNTIME"); [ "$RUNTIME" != rancher ] || ENGINE=(docker --context rancher-desktop)
ARGS=(run --rm --init --user "$(id -u):$(id -g)" --cap-drop ALL --security-opt no-new-privileges --read-only --tmpfs "/tmp:rw,nosuid,nodev" --workdir /workspace --mount "type=bind,src=$WORKTREE,dst=/workspace")
[ "$(id -u)" != 0 ] || { echo 'isolated workers require a non-root caller' >&2; exit 78; }
while IFS= read -r NAME; do
  [ -n "$NAME" ] || continue
  if [ "$MODE" = run ] && [ -z "${!NAME:-}" ]; then echo "required credential variable missing: $NAME" >&2; exit 78; fi
  ARGS+=(--env "$NAME")
done < <(jq -r '.credential_names[]' <<< "$PLAN")
HOSTS=$(jq -r '.egress_allowlist[]' <<< "$PLAN")
if [ "$MODE" = render ]; then
  jq -cn --arg runtime "$RUNTIME" --arg worktree "$WORKTREE" --arg image "$IMAGE" --arg user "$(id -u):$(id -g)" --argjson profile "$PLAN" --argjson args "$(printf '%s\n' "${ARGS[@]}" "$IMAGE" "$@" | jq -Rs 'split("\n")[:-1]')" '{runtime:$runtime,disposable:true,user:$user,worktree:$worktree,image:$image,network:(if ($profile.egress_allowlist|length)>0 then "internal-proxy" else "none" end),profile:$profile,args:$args,executable_plan:false}'
  exit
fi
command -v "${ENGINE[0]}" >/dev/null 2>&1 || { echo 'selected container runtime unavailable' >&2; exit 69; }
# Engine inherits only transport settings and explicitly selected worker secrets.
engine() (
  while IFS= read -r NAME; do export -n "${NAME?}"; done < <(compgen -e)
  export PATH HOME TMPDIR
  for NAME in DOCKER_HOST DOCKER_CONTEXT DOCKER_CONFIG DOCKER_TLS_VERIFY DOCKER_CERT_PATH CONTAINER_HOST XDG_RUNTIME_DIR; do
    [ -z "${!NAME:-}" ] || export "${NAME?}"
  done
  while IFS= read -r NAME; do [ -z "$NAME" ] || export "${NAME?}"; done < <(jq -r '.credential_names[]' <<< "$PLAN")
  "${ENGINE[@]}" "$@"
)
NET=""; PROXY=""; WORKER=""; SCRATCH=""
cleanup() {
  [ -z "$WORKER" ] || engine rm -f "$WORKER" >/dev/null 2>&1 || true
  [ -z "$PROXY" ] || engine rm -f "$PROXY" >/dev/null 2>&1 || true
  [ -z "$NET" ] || engine network rm "$NET" >/dev/null 2>&1 || true
  if [ -n "$SCRATCH" ]; then rm -f "$SCRATCH/squid.conf"; rmdir "$SCRATCH"; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
WORKER="nightshift-worker-$$-$RANDOM"
if [ -n "$HOSTS" ]; then
  [ "$RUNTIME" != podman ] || { echo 'Podman online profiles unavailable: host-isolated gateway enforcement is not implemented; use offline or Docker/Rancher' >&2; exit 78; }
  [ -n "${NIGHTSHIFT_PROXY_IMAGE:-}" ] || { echo 'NIGHTSHIFT_PROXY_IMAGE required for egress enforcement (image must provide squid)' >&2; exit 78; }
  NET="nightshift-egress-$$-$RANDOM"; PROXY="$NET-proxy"
  SCRATCH=$(mktemp -d "${TMPDIR:-/tmp}/nightshift-proxy.XXXXXX")
  # Generated config contains validated hostnames only, no credentials.
  {
    printf '%s\n' 'http_port 3128' 'pid_filename /tmp/squid.pid' 'cache_log /dev/null' 'access_log none' 'cache deny all' 'coredump_dir /tmp' 'visible_hostname nightshift-proxy'
    printf '%s\n' 'acl CONNECT method CONNECT' 'acl tls_port port 443' 'acl private_dst dst 0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 192.168.0.0/16 224.0.0.0/4 ::/128 ::1/128 fc00::/7 fe80::/10'
    printf 'acl allowed dstdomain -n'; while IFS= read -r HOST; do printf ' %s' "$HOST"; done <<< "$HOSTS"; printf '\n'
    printf '%s\n' 'http_access deny !allowed' 'http_access deny private_dst' 'http_access allow CONNECT tls_port allowed' 'http_access deny all'
  } > "$SCRATCH/squid.conf"
  chmod 644 "$SCRATCH/squid.conf"
  # Older engines may accept unknown options; require a supporting version.
  ENGINE_MAJOR=$(engine version --format '{{.Server.Version}}' | cut -d. -f1)
  case "$ENGINE_MAJOR" in ''|*[!0-9]*) echo 'cannot verify Docker engine version' >&2; exit 78;; esac
  [ "$ENGINE_MAJOR" -ge 28 ] || { echo 'online profiles require Docker Engine 28+ isolated gateway mode' >&2; exit 78; }
  engine network create --internal --ipv6=false --opt com.docker.network.bridge.gateway_mode_ipv4=isolated "$NET" >/dev/null
  engine create --name "$PROXY" --network bridge --user "$(id -u):$(id -g)" --cap-drop ALL --security-opt no-new-privileges --read-only --tmpfs /tmp:rw,nosuid,nodev --mount "type=bind,src=$SCRATCH/squid.conf,dst=/etc/squid/squid.conf,readonly" --entrypoint squid "$NIGHTSHIFT_PROXY_IMAGE" -N -f /etc/squid/squid.conf >/dev/null
  engine network connect "$NET" "$PROXY"
  engine start "$PROXY" >/dev/null
  PROXY_IP=$(engine inspect "$PROXY" | jq -er --arg net "$NET" '.[0].NetworkSettings.Networks[$net].IPAddress | select(test("^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+$"))')
  # No external route. DNS targets the proxy IP, which has no DNS listener.
  ARGS+=(--network "$NET" --dns "$PROXY_IP" --env "HTTPS_PROXY=http://$PROXY_IP:3128" --env "HTTP_PROXY=http://$PROXY_IP:3128" --env "https_proxy=http://$PROXY_IP:3128" --env "http_proxy=http://$PROXY_IP:3128" --env NO_PROXY= --env no_proxy=)
else
  ARGS+=(--network none)
fi
engine "${ARGS[@]}" --name "$WORKER" "$IMAGE" "$@"
