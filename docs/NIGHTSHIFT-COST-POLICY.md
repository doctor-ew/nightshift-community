# Authentication and usage policy

The terminal factory launcher defaults to subscription authentication. Hosted
API billing requires explicit per-run --auth api; do not use it as a workaround
for expired login or exhausted subscription usage.

Each participant uses their own authorized account. Subscription access is not
unlimited and does not disable provider-account extra usage. Check account
settings and event arrangements separately. Never share keys or session tokens.

The launcher removes selected inherited billing credentials and checks hosted
login status. This is not an account-wide spending firewall or a guarantee about
arbitrary subprocesses, credential helpers or directly launched coding sessions.
See scripts/nightshift-factory.sh and tests/test-factory-auth.sh for implementation
and mocked regression coverage.

Local inference is optional and experimental in this pilot. Missing usage or
cost information means unknown, not zero. Do not weaken tests, security policy
or independent review to stay within a usage budget.
