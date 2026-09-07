#!/usr/bin/env bash
# Print only: installing this snippet in a persistent scheduler is opt-in.
set -euo pipefail
exec python3 - "$0" "$@" <<'PY'
import os
from pathlib import Path
import shlex
import sys

try:
    args = sys.argv[2:]
    if len(args) != 2 or args[0] != '--project' or not args[1]:
        raise ValueError('usage: nightshift-harness-audit-cron.sh --project DIR')
    path = os.environ.get('PATH', '')
    if any(c in args[1] or c in path for c in ('\n', '\r')):
        raise ValueError('project and PATH must not contain newlines')
    project = Path(args[1]).resolve()
    audit = Path(sys.argv[1]).resolve().with_name('nightshift-harness-audit.sh')
    if not project.is_dir():
        raise ValueError('project directory does not exist')
    if any(c in str(project) or c in str(audit) for c in ('\n', '\r')):
        raise ValueError('resolved paths must not contain newlines')
    # Keep cron's environment parser away from user-provided quoting. The
    # absolute env executable restores the exact captured PATH for the audit.
    print('PATH=/usr/bin:/bin')
    command = ' '.join(shlex.quote(arg) for arg in ['/usr/bin/env', 'PATH=' + path, str(audit), '--project', str(project), '--monthly', '--refresh'])
    # Cron removes this backslash before passing a percent to the POSIX shell.
    print('0 9 1 * * ' + command.replace('%', '\\%'))
except (OSError, ValueError, RuntimeError) as error:
    print('nightshift-harness-audit-cron: ' + str(error), file=sys.stderr)
    sys.exit(1)
PY
