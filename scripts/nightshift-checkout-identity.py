#!/usr/bin/env python3
"""Cached checkout identity: (top-level, common git dir) for a path, per process.

Nightshift loads its scripts afresh via importlib on every call, so the cache lives
in a registry in sys.modules. An entry is reused only while the checkout is provably
the same one: the device and inode of <top>/.git and of the common directory, and
the content of a worktree's .git pointer file, must all still match.
"""
from pathlib import Path
import subprocess
import sys

_CACHE = sys.modules.setdefault('_nightshift_checkout_cache', type(sys)('_nightshift_checkout_cache')).__dict__.setdefault('entries', {})


def _fingerprint(top, common):
    try:
        marker = top / '.git'; a = marker.stat(); b = common.stat()
        pointer = marker.read_text() if marker.is_file() else ''
        return (a.st_dev, a.st_ino, b.st_dev, b.st_ino, pointer)
    except OSError:
        return None


def checkout_identity(project):
    """(top, common) for a checkout, or None when the path is not inside one."""
    key = str(project)
    cached = _CACHE.get(key)
    if cached and _fingerprint(cached[0], cached[1]) == cached[2]:
        return cached[0], cached[1]
    result = subprocess.run(['git', '-C', key, 'rev-parse', '--path-format=absolute', '--show-toplevel', '--git-common-dir'],
                            capture_output=True, text=True, timeout=5)
    if result.returncode != 0:
        _CACHE.pop(key, None)
        return None
    top, common = map(Path, result.stdout.splitlines()[:2])
    print_ = _fingerprint(top, common)
    if print_ is not None:
        _CACHE[key] = (top, common, print_)
    return top, common
