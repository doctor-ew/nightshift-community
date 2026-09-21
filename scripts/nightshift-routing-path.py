#!/usr/bin/env python3
"""Resolve specialist routing even when an agent shell drops inherited env."""
import os
from pathlib import Path
import subprocess
import sys
import tomllib


def resolve(root):
    explicit = os.environ.get('NIGHTSHIFT_ROUTING_FILE')
    if explicit:
        path = Path(explicit).resolve()
    else:
        project = os.environ.get('NIGHTSHIFT_PROJECT_DIR')
        if not project:
            result = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
            project = result.stdout.strip() if result.returncode == 0 else str(Path.cwd())
        project = Path(project).resolve()
        manifest = project / '.nightshift.toml'
        settings = tomllib.loads(manifest.read_text()) if manifest.exists() else {}
        configured = settings.get('routing', {}).get('file') or settings.get('providers', {}).get('routing_file')
        path = (project / configured).resolve() if configured else Path(root).resolve() / 'routing.json'
    if not path.is_file():
        raise ValueError('Configured routing file is missing: ' + str(path))
    return path


if __name__ == '__main__':
    try:
        print(resolve(sys.argv[1]))
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
