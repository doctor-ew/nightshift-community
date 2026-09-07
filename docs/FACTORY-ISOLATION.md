# Factory worker isolation

`scripts/nightshift-isolate.sh run` invokes a disposable container for each command. Required image: `--image` or `NIGHTSHIFT_WORKER_IMAGE`. Runtime: `--runtime` or `NIGHTSHIFT_CONTAINER_RUNTIME`, with `auto` choosing installed Docker first, then Podman. An unavailable selected daemon fails the command; execution never falls back to the host. `rancher` selects `docker --context rancher-desktop` and requires Rancher Desktop's Moby engine. Containerd/nerdctl is unsupported.

The worker mounts the assigned worktree at `/workspace`, runs with the caller's non-root UID/GID (so worktree files remain writable), drops capabilities, enables no-new-privileges, and has a read-only image plus ephemeral `/tmp`. Root callers are rejected. Images must support this UID and contain the required tooling; project files, including any project-local secrets, are visible because the worktree is explicitly mounted. Host homes and the container socket are never mounted. Trusted image maintainers must not bake credentials into images.

The default `offline` profile uses `--network none`. Direct `bridge` and `host` networking are rejected. Docker, Podman, and Rancher support this offline path.

Online profiles require `NIGHTSHIFT_PROXY_IMAGE`, a trusted image with Squid 5–7 executable as `squid` and capable of running under the caller's UID with a writable `/tmp`. Pin worker and proxy images by digest in deployment configuration. The wrapper starts Squid with generated exact-domain ACLs, an internal worker network, and a separate external connection for the proxy. It permits CONNECT only to port 443 on explicitly configured domains, denies private/link-local destinations and IP literals, and denies all other requests. Clients must honor HTTPS proxy variables; arbitrary protocols and plain HTTP are unsupported and fail closed.

Docker/Rancher online mode requires Docker Engine 28+ and uses internal `gateway_mode_ipv4=isolated` with IPv6 disabled. An ordinary internal bridge can still expose host services through its gateway; isolated gateway mode removes that host bridge address. Worker DNS points to the proxy's internal IP, which exposes no DNS service. Ignoring proxy variables therefore does not grant an external network route. Podman online profiles fail closed because an equivalent host-gateway isolation backend has not been implemented.

Reference: [Docker gateway modes](https://docs.docker.com/engine/network/port-publishing/#gateway-modes), [Squid ACL semantics](https://www.squid-cache.org/Doc/config/acl/), and [Rancher Desktop engine selection](https://docs.rancherdesktop.io/ui/preferences/container-engine/general/).

Resources are removed on success, failure, INT, and TERM; a SIGKILL/daemon crash can leave named `nightshift-worker-*` / `nightshift-egress-*` resources for operator cleanup. A proxy startup/configuration failure provides no permissive fallback. The host daemon, image, and firewall configuration remain trusted infrastructure.

Validation: mock tests cover runtime arguments, credential filtering, missing-variable rejection, private topology, and cleanup. The development machine's Docker daemon was unavailable during this change, so real allowed/denied traffic and container compatibility have NOT been verified. Do not treat passing mock tests as an operational egress audit.
