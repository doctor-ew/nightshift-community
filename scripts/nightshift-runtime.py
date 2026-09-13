"""Bounded runtime discovery. Keep shim dispatch distinct from binary identity."""
import os
from pathlib import Path
import shutil
import subprocess


def executable(name):
    path = shutil.which(name)
    if not path:
        raise ValueError(f'{name} is not installed')
    # Resolving a mise shim's symlink changes argv[0] to mise and loses dispatch.
    if 'mise' in path and 'shims' in Path(path).parts:
        mise = shutil.which('mise')
        if not mise:
            raise ValueError('mise shim found but mise is unavailable')
        result = subprocess.run([mise, 'which', name], capture_output=True, text=True,
                                timeout=5, stdin=subprocess.DEVNULL)
        candidate = Path(result.stdout.strip())
        if result.returncode or not candidate.is_absolute() or not candidate.is_file() or not os.access(candidate, os.X_OK):
            raise ValueError(f'cannot resolve mise runtime {name}')
        path = str(candidate)
    return os.path.abspath(path)
