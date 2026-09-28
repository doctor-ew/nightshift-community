#!/usr/bin/env python3
"""Cached checkout identity: (top-level, common git dir) for a path, per process.

Nightshift loads its scripts afresh via importlib on every call, so the cache lives
in a registry in sys.modules. An entry is reused only while every input git uses
to answer is provably unchanged:
- the git discovery environment (part of the cache key);
- where the path resolves to (a repointed symlink is a different checkout);
- no .git entry has appeared between the path and the cached top level (a nested
  repository would now own the path);
- the type, device and inode of <top>/.git and of the common directory, and the
  content of a worktree's .git pointer file.
A repository recreated at the same path has the same answer, so reuse there is
correct even when the filesystem reuses the inode.
"""
import os
from pathlib import Path
import subprocess
import sys

_CACHE = sys.modules.setdefault('_nightshift_checkout_cache', type(sys)('_nightshift_checkout_cache')).__dict__.setdefault('entries', {})
_GIT_ENV = ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_CEILING_DIRECTORIES', 'GIT_DISCOVERY_ACROSS_FILESYSTEM')


def _fingerprint(project, top, common):
    try:
        real = Path(os.path.realpath(project))
        # Compare directories by filesystem identity, not spelling: git reports the
        # on-disk case, which differs from the query on case-insensitive filesystems.
        for directory in (real, *real.parents):
            if os.path.samefile(directory, top):
                break
            if os.path.lexists(directory / '.git'):
                return None
        else:
            return None
        marker = top / '.git'; a = marker.lstat(); b = common.stat()
        pointer = marker.read_text() if marker.is_file() else ''
        return (str(real), a.st_mode, a.st_dev, a.st_ino, b.st_dev, b.st_ino, pointer)
    except OSError:
        return None


def checkout_identity(project):
    """(top, common) for a checkout, or None when the path is not inside one."""
    key = (str(project),) + tuple(os.environ.get(name) for name in _GIT_ENV)
    cached = _CACHE.get(key)
    if cached and _fingerprint(project, cached[0], cached[1]) == cached[2]:
        return cached[0], cached[1]
    result = subprocess.run(['git', '-C', str(project), 'rev-parse', '--path-format=absolute', '--show-toplevel', '--git-common-dir'],
                            capture_output=True, text=True, timeout=5)
    if result.returncode != 0:
        _CACHE.pop(key, None)
        return None
    top, common = map(Path, result.stdout.splitlines()[:2])
    print_ = _fingerprint(project, top, common)
    if print_ is not None:
        _CACHE[key] = (top, common, print_)
    else:
        _CACHE.pop(key, None)
    return top, common
