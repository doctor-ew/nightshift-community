#!/usr/bin/env python3
"""Verify the retained public talk fixture; block every provider generation command."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
REVISION = '201970d9f8deabdf3d978297b2d035290d4f2edf'
TASK = 'spec-014c777fd4684e19'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def command(argv, env, cwd, log):
    result = subprocess.run(argv, env=env, cwd=cwd, capture_output=True, text=True, timeout=120)
    log.write_text(result.stdout + result.stderr)
    require(result.returncode == 0, 'command_failed:' + str(log))
    return result


def verify(pipeline, project, task):
    state = pipeline.snapshot(project, task)
    require(state and state.get('status') == 'complete' and state.get('next_action') == 'none', 'controller_not_complete')
    target = Path(state['worktree'])
    require(target.is_dir(), 'preserved_worktree_missing')
    require(set(state['completed']) == set(pipeline.STAGES), 'six_accepted_stages_required')
    hashes = {}
    for stage in pipeline.STAGES:
        row = state['completed'][stage]
        require(digest(row['receipt']) == row['sha256'], 'receipt_changed:' + stage)
        require(pipeline.inputs(target, task, stage, state) == row['input_sha256'], 'stage_inputs_changed:' + stage)
        require(pipeline.validate_receipt(row['receipt'], task, stage, target)['status'] == 'pass', 'stage_not_passed:' + stage)
        hashes[stage] = row['sha256']
    return state, target, hashes


def guards(directory, env, blocked):
    """Only subscription authentication probes may reach the real provider CLI."""
    binaries = {name: shutil.which(name, path=env['PATH']) for name in ('codex', 'claude')}
    require(all(binaries.values()), 'subscription_runtime_missing')
    for name in binaries:
        program = directory / name
        program.write_text('#!' + sys.executable + '\n' +
            'import json,os,pathlib,sys\n' +
            'name=pathlib.Path(sys.argv[0]).name\n' +
            'allowed={"codex":["login","status"],"claude":["auth","status","--json"]}\n' +
            'if sys.argv[1:]==allowed[name]:\n' +
            ' real=' + repr(binaries) + '[name]\n os.execv(real,[real,*sys.argv[1:]])\n' +
            'with open(' + repr(str(blocked)) + ',"a") as stream: stream.write(json.dumps({"provider":name,"status":"generation_blocked"})+"\\n")\n' +
            'sys.exit(75)\n')
        program.chmod(0o700)
    return dict(env, PATH=str(directory) + os.pathsep + env['PATH'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, default=ROOT / '.nightshift/133-runtime')
    parser.add_argument('--project', type=Path, default=Path('/private/tmp/nightshift-certification-133'))
    parser.add_argument('--output', type=Path, default=ROOT / '.nightshift/135/testing')
    parser.add_argument('--check-only', action='store_true', help='Skip subscription authentication and the guarded cached CLI repeat')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.output = Path(tempfile.mkdtemp(prefix='check-', dir=args.output)).resolve()
    runtime = args.runtime_root.resolve()
    source = runtime / 'source'
    require(args.project.is_dir(), 'preserved_public_project_missing')
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    require(revision == REVISION, 'pinned_revision_changed')
    require(not subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip(), 'pinned_source_dirty')
    require((runtime / 'runtime/scripts/nightshift-pipeline.py').resolve() == source / 'scripts/nightshift-pipeline.py', 'installed_controller_identity_changed')
    links = read(runtime / 'runtime/install-links.json')
    require(bool(links), 'installation_manifest_missing')
    for installed, original in links.items():
        installed, original = Path(installed), Path(original)
        require(installed.is_relative_to(runtime) and original.is_relative_to(source), 'installation_boundary_changed')
        require(installed.exists() and installed.resolve() == original.resolve(), 'installation_link_changed:' + str(installed))
    env = dict(os.environ, NIGHTSHIFT_HOME=str(runtime / 'runtime'), NIGHTSHIFT_SYNC_CHECK='off', NIGHTSHIFT_GEAR='1',
               NIGHTSHIFT_JEV_ENABLED='false', PYTHONDONTWRITEBYTECODE='1', NIGHTSHIFT_EFFICIENCY_DIR=str(runtime / 'efficiency'))
    env.pop('NIGHTSHIFT_JEV_INPUT', None)
    # Helpers import and subprocess with the same configuration as the talk wrapper.
    os.environ.update(env)
    pipeline = module(source / 'scripts/nightshift-pipeline.py', 'talk_pipeline')
    budget = module(source / 'scripts/nightshift-ticket-budget.py', 'talk_budget')
    state, target, hashes = verify(pipeline, args.project, TASK)
    ledger = budget.ledger_path(args.project, TASK)
    before_budget = read(ledger)
    before = dict(completed=state['completed'], attempts=state['attempts'], receipts=hashes, reservations=before_budget['reservations'])
    (args.output / 'before.json').write_text(json.dumps(before, indent=2) + '\n')
    command(['bash', str(source / 'scripts/nightshift-worktree.sh'), 'check', TASK, '--project', str(args.project)], env, args.project, args.output / 'worktree.log')
    for gate in ('development', 'final'):
        result = command([sys.executable, str(source / 'scripts/nightshift-behavior-proof.py'), 'gate', '--project', str(target), '--task', TASK, '--gate', gate], env, target, args.output / (gate + '-proof.log'))
        require(json.loads(result.stdout).get('outcome') == 'pass', 'proof_not_passed:' + gate)
    command([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], env, target, args.output / 'unit-tests.log')
    repeated = False
    if not args.check_only:
        settings = read(args.project / '.git/nightshift/console' / (TASK + '.json'))['settings']
        require(settings == dict(ref='spec:brief.md', provider='codex', model='gpt-6.1-sol', policy='standard', auth='subscription', branch='auto', base='main', push=False, pr=False), 'recorded_policy_changed')
        with tempfile.TemporaryDirectory(prefix='nightshift-talk-generation-guard-') as temporary:
            binary = Path(temporary)
            probe = args.output / 'guard-self-test.jsonl'
            probe_env = guards(binary, env, probe)
            result = subprocess.run([str(binary / 'codex'), 'exec', 'sealed-no-call-probe'], env=probe_env, capture_output=True, timeout=5)
            require(result.returncode == 75, 'generation_guard_failed')
            blocked = args.output / 'blocked-generation.jsonl'
            repeat_env = guards(binary, env, blocked)
            verify(pipeline, args.project, TASK)
            command(['bash', str(runtime / 'nightshift-talk.sh'), 'spec:brief.md', '--provider', 'codex', '--model', 'gpt-6.1-sol', '--auth', 'subscription', '--branch', 'auto', '--base', 'main', '--gear', '1', '--dashboard', 'off'], repeat_env, args.project, args.output / 'cached-repeat.log')
            require(not blocked.exists() or not blocked.read_text(), 'repeat_attempted_generation')
            repeated = True
    after_state, _, after_hashes = verify(pipeline, args.project, TASK)
    after_budget = read(ledger)
    after = dict(completed=after_state['completed'], attempts=after_state['attempts'], receipts=after_hashes, reservations=after_budget['reservations'])
    (args.output / 'after.json').write_text(json.dumps(after, indent=2) + '\n')
    require(before == after, 'retained_receipts_attempts_or_reservations_changed')
    report = dict(status='pass', revision=revision, task=TASK, stages=len(hashes), proof_gates='pass', unit_tests='pass', cached_repeat=repeated,
                  accepted_receipts_unchanged=True, attempts_unchanged=True, reservations_unchanged=True,
                  reservations=len(before_budget['reservations']), additional_provider_calls=0, output=str(args.output))
    (args.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='fail', reason=str(error))))
        raise SystemExit(1)
