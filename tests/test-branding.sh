#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 - "$ROOT" <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
# Fragments keep the regression fixture itself free of retired product names.
retired = re.compile('|'.join(('cx' + 'eng', 'con' + 'nexure', 'drew' + r'[-_ ]pipeline', 'drew' + '-')), re.I)
files = [root / name for name in ('README.md', 'CLAUDE.md', 'AGENTS.md', 'install.sh', '.gitignore')]
for directory in ('scripts', 'commands', 'agents', 'skills', 'compat', 'tests'):
    files.extend(p for p in (root / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
files.extend((root / 'docs').glob('*.md'))
bad = []
for path in files:
    if not path.exists():
        continue
    if retired.search(str(path.relative_to(root))):
        bad.append(str(path.relative_to(root)))
    try:
        for line, value in enumerate(path.read_text().splitlines(), 1):
            if retired.search(value):
                bad.append(f'{path.relative_to(root)}:{line}')
    except UnicodeError:
        pass
if bad:
    sys.exit('Retired branding in maintained source: ' + ', '.join(bad))
print('PASS: maintained Nightshift source has no retired branding or alias paths')
PY
FIXTURE=$(mktemp -d "${TMPDIR:-/tmp}/nightshift-install-identity.XXXXXX")
trap 'rm -rf "$FIXTURE"' EXIT
mkdir -p "$FIXTURE/claude/commands" "$FIXTURE/codex/skills" "$FIXTURE/bin"
ln -s "$ROOT/compat/commands/retired-eng.md" "$FIXTURE/claude/commands/retired-eng.md"
ln -s "$ROOT/compat/skills/retired" "$FIXTURE/codex/skills/retired"
ln -s "$ROOT/scripts/nightshift-factory.sh" "$FIXTURE/bin/retired"
ln -s /unrelated/user/target "$FIXTURE/bin/unrelated"
bash "$ROOT/install.sh" --runtime all --target "$FIXTURE/claude" \
  --codex-target "$FIXTURE/codex" --nightshift-target "$FIXTURE/runtime" \
  --bin-target "$FIXTURE/bin" --auth subscription > "$FIXTURE/install.log" 2>&1
test ! -L "$FIXTURE/bin/retired"
test ! -L "$FIXTURE/codex/skills/retired"
test ! -L "$FIXTURE/claude/commands/retired-eng.md"
test -L "$FIXTURE/bin/unrelated"
test -L "$FIXTURE/bin/nightshift"
test -L "$FIXTURE/runtime/scripts/nightshift-setup.py"
test "$(find "$FIXTURE/runtime/.backup" -path '*/retired/*' -type l | wc -l | tr -d ' ')" = 3
echo 'PASS: installer archives owned aliases and preserves unrelated symlinks'
