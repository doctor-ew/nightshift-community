#!/usr/bin/env python3
"""Bounded, model-free MEX dependency and graph preparation for init."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

PACKAGE = 'mex-agent@0.8.2'


def install_directory():
    return Path(os.environ.get('NIGHTSHIFT_HOME', str(Path.home()/'.nightshift')))/'tools/mex'


def binary():
    system = shutil.which('mex')
    local = install_directory()/'node_modules/.bin/mex'
    return system or (str(local) if local.is_file() and os.access(local, os.X_OK) and (install_directory()/'nightshift-installed.json').is_file() else None)


def run(argv, project, deadline):
    remaining = deadline-time.monotonic()
    if remaining <= 0:
        raise TimeoutError('MEX initialization time limit reached')
    proc = subprocess.Popen(argv, cwd=project, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=remaining)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL); proc.communicate()
        raise TimeoutError('MEX initialization time limit reached')
    if proc.returncode:
        raise ValueError('MEX command failed: '+(err or out)[-1500:])
    if len(out.encode()) > 128000:
        raise ValueError('MEX status exceeds output bound')
    return out


def prepare(project, timeout=60, install=True):
    start = time.monotonic(); deadline = start+timeout
    result = {'status': 'unavailable', 'action': 'none', 'model_started': False}
    try:
        executable = binary()
        if not executable:
            if not install:
                raise ValueError('MEX is not installed')
            npm = shutil.which('npm')
            if not npm:
                raise ValueError('npm is required to install '+PACKAGE)
            result['action'] = 'install'
            run([npm, 'install', '--prefix', str(install_directory()), '--no-audit', '--no-fund', PACKAGE], project, deadline)
            install_directory().mkdir(parents=True, exist_ok=True)
            (install_directory()/'nightshift-installed.json').write_text(json.dumps({'package': PACKAGE}))
            executable = binary()
            if not executable:
                raise ValueError('MEX installation did not provide an executable')
        def status():
            value = json.loads(run([executable, 'graph', 'status', '--json', '--root', str(project)], project, deadline))
            if not isinstance(value, dict):
                raise ValueError('MEX status requires an object')
            return value
        before = status(); result['previous_status'] = before.get('status')
        if before.get('status') == 'fresh':
            result.update(status='ready', action='reuse', graph=before)
        else:
            if before.get('status') == 'missing' and not (Path(project)/'.mex/graph.db').exists():
                action = 'rebuild'
            elif before.get('status') == 'stale':
                action = 'refresh'
            else:
                result['graph'] = before
                raise ValueError('MEX requires explicit maintenance; existing graph preserved')
            result['action'] = action
            run([executable, 'graph', action, '--json', '--root', str(project)], project, deadline)
            after = status(); result['graph'] = after
            if after.get('status') != 'fresh':
                raise ValueError('MEX graph is not fresh after '+action)
            result['status'] = 'ready'
    except (OSError, ValueError, TimeoutError) as error:
        result['reason'] = str(error)
    result['elapsed_seconds'] = round(time.monotonic()-start, 3)
    return result
