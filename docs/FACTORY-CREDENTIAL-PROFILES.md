# Factory credential and egress profiles

`scripts/nightshift-credentials.sh plan` validates a selected profile and returns names only. `scripts/nightshift-isolate.sh run` checks each required variable is nonempty, then passes only its name through the container engine's `--env` option. Secret values remain in the process environment, never the plan or argument list. The engine process receives only selected variables plus necessary runtime transport settings. Environment values are still accessible to the container engine administrator and to the worker receiving them; this is not a secret vault.

Select with `--profile` / `NIGHTSHIFT_CREDENTIAL_PROFILE`; supply configuration with `--profiles` / `NIGHTSHIFT_PROFILES_FILE`. With no configuration, only `offline` exists, with no credentials or networking. No placeholder hosts or implicit ticket, repository, or production credentials are supplied.

The JSON configuration has a top-level `profiles` object, keyed by profile name. Each entry requires `credential_names` (array of required environment variable names) and `egress_allowlist` (array of exact DNS hostnames); optional `production` is a boolean defaulting to false. Store variable names, never secret values. Shell/runtime override variable names, IP literals, wildcard hosts, malformed hosts, and `.invalid` placeholders are rejected. Nonempty egress requires the enforcing backend described in [Factory isolation](FACTORY-ISOLATION.md).

For example, a repository-specific profile may select `GH_TOKEN` with only `github.com` and `api.github.com` if those endpoints are actually needed. Avoid copying a generic provider host list; configure the endpoints your selected authentication method and tool require. A ChatGPT/Claude subscription login is not an API key; these profiles do not convert login sessions or mount an entire host credential home. Subscription session transfer into containers requires a separately designed credential mechanism and is not provided here.

A profile named `production`, or with `production: true`, requires the existing production policy decision and fresh confirmation. The planner does not invent authorization. All other credential profiles remain operator-controlled configuration, so names alone do not classify a secret's privileges.

Tests validate profile schema, placeholder/injection rejection, explicit environment injection, and production denial/confirmation. Online Podman enforcement and live Docker traffic verification remain outstanding; both limitations are explicitly recorded in the isolation documentation.
