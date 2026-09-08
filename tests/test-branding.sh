#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 - "$ROOT" <<'PY'
from pathlib import Path
import hashlib, importlib.util, json, os, re, runpy, shutil, subprocess, sys, tempfile, unittest
ROOT=Path(sys.argv.pop(1)).resolve()
SCANNER=ROOT/'scripts/nightshift-branding.py'
INVENTORY=ROOT/'scripts/nightshift-install-inventory.py'
RETIRED='cx'+'eng'
SECRET='PRIVATE_FIXTURE_SENTINEL_72e4'

class BrandingContract(unittest.TestCase):
    def setUp(self):
        if not SCANNER.is_file() or not INVENTORY.is_file():
            self.skipTest('UNIMPLEMENTED scanner/inventory; not behavioral RED evidence')
        self.tmp=tempfile.TemporaryDirectory(prefix='nightshift-branding-contract-');self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name).resolve();self.source=self.base/'source'
        shutil.copytree(ROOT,self.source,ignore=shutil.ignore_patterns('.git','.nightshift','__pycache__','node_modules'))
        self.targets={key:self.base/key for key in ('claude','codex','nightshift','bin')}
        self.env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
        self.forbidden=self.base/'forbidden';self.forbidden.mkdir();(self.forbidden/'private.txt').write_text(SECRET)

    def args(self,inventory='source',runtime='all'):
        args=['--project',str(self.source),'--inventory',inventory]
        if inventory!='source':
            args+=['--runtime',runtime,'--target',str(self.targets['claude']),'--codex-target',str(self.targets['codex']),'--nightshift-target',str(self.targets['nightshift']),'--bin-target',str(self.targets['bin'])]
        return args

    def scan(self,inventory='source',runtime='all',forbidden=()):
        # CPython audit events establish absence of reads/listing, not merely writes.
        guarded=[str(self.forbidden),*(str(p) for p in forbidden)]
        wrapper='''import json,os,runpy,sys
script=sys.argv[1]; forbidden=json.loads(sys.argv[2]); sys.argv=[script]+sys.argv[3:]
def audit(event,args):
 if event in ('open','os.scandir','os.listdir') and args and isinstance(args[0],(str,bytes)):
  path=os.fsdecode(args[0]); physical=os.path.realpath(path)
  if any(physical==root or physical.startswith(root+os.sep) for root in forbidden):
   os.write(2,b'FORBIDDEN_READ\\n');raise RuntimeError('forbidden read')
sys.addaudithook(audit);runpy.run_path(script,run_name='__main__')
'''
        result=subprocess.run([sys.executable,'-c',wrapper,str(self.source/'scripts/nightshift-branding.py'),json.dumps(guarded),*self.args(inventory,runtime)],env=self.env,capture_output=True,text=True)
        self.assertNotIn('FORBIDDEN_READ',result.stderr)
        self.assertNotIn(SECRET,result.stdout+result.stderr)
        self.assertNotIn(str(self.base),result.stdout)
        self.assertNotIn(str(self.forbidden),result.stderr)
        try: payload=json.loads(result.stdout)
        except ValueError: self.fail('Scanner did not emit one JSON object: '+repr(result.stdout+result.stderr))
        self.assertIn('findings',payload);self.assertIn('coverage',payload);self.assertIn('inventories',payload)
        return result,payload

    def entries(self,runtime='all'):
        argv=[sys.executable,str(self.source/'scripts/nightshift-install-inventory.py'),'--project',str(self.source),'--runtime',runtime,'--target',str(self.targets['claude']),'--codex-target',str(self.targets['codex']),'--nightshift-target',str(self.targets['nightshift']),'--bin-target',str(self.targets['bin'])]
        result=subprocess.run(argv,env=self.env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        payload=json.loads(result.stdout);self.assertEqual(payload['version'],1)
        return payload['entries']

    def installed(self,mode='copy',runtime='all'):
        entries=self.entries(runtime);ownership={}
        for entry in entries:
            source=Path(entry['source']);dest=Path(entry['destination']);dest.parent.mkdir(parents=True,exist_ok=True)
            if mode=='symlink':dest.symlink_to(source,target_is_directory=entry['kind']=='tree')
            elif entry['kind']=='tree':shutil.copytree(source,dest)
            else:shutil.copy2(source,dest)
            ownership[str(dest)]=str(source)
        self.targets['nightshift'].mkdir(exist_ok=True)
        self.ownership=self.targets['nightshift']/'install-links.json';self.ownership.write_text(json.dumps(ownership))
        return entries,ownership

    def snapshot(self):
        result={}
        for path in self.base.rglob('*'):
            rel=str(path.relative_to(self.base))
            if path.is_symlink():result[rel]=('link',os.readlink(path))
            elif path.is_file():result[rel]=('file',hashlib.sha256(path.read_bytes()).hexdigest())
            else:result[rel]=('dir',)
        return result

    def finding(self,payload,path,line):
        matches=[f for f in payload['findings'] if f.get('path')==path and f.get('line')==line]
        self.assertTrue(matches,(path,line,payload['findings']))
        for f in matches:self.assertTrue(f.get('rule'));self.assertTrue(f.get('inventory'))

    def test_source_clean_and_readonly(self):
        before=self.snapshot();result,_=self.scan();self.assertEqual(result.returncode,0,result.stdout)
        self.assertEqual(self.snapshot(),before)

    def test_nested_name_content_and_sanitization(self):
        nested=self.source/'docs/nested-fixture';nested.mkdir()
        (nested/'example.md').write_text('ordinary\n'+RETIRED+' '+SECRET+'\n')
        (nested/(RETIRED+'\nname.md')).write_text('ordinary\n')
        result,payload=self.scan();self.assertEqual(result.returncode,1)
        self.finding(payload,'docs/nested-fixture/example.md',2)
        self.finding(payload,'docs/nested-fixture/'+RETIRED+'\nname.md',0)

    def test_provider_core_rules_and_negative_instructions(self):
        path=self.source/'commands/nightshift-fixture.md'
        bad=['Invoke '+'mcp__claude_ai_Test__readPage'+' now.','These checks are run inline by '+'Claude'+' using Read + Grep.']
        for text in bad:
            with self.subTest(text=text):
                path.write_text(text+'\n');result,payload=self.scan();self.assertEqual(result.returncode,1)
                self.finding(payload,'commands/nightshift-fixture.md',1)
        path.write_text('Do not invoke gstack commands.\n')
        role=self.source/'agents/nightshift-fixture.md';role.write_text('---\nname: nightshift-fixture\nmodel: fixed-model\n---\n')
        result,payload=self.scan();self.assertEqual(result.returncode,1);self.finding(payload,'agents/nightshift-fixture.md',3)
        role.write_text('---\nname: nightshift-fixture\n# model: explanation only\n---\n')
        result,_=self.scan();self.assertEqual(result.returncode,0,result.stdout)

    def policy_exception(self):
        policy=self.source/'scripts/nightshift-branding-policy.json'
        data=json.loads(policy.read_text())
        self.assertEqual(data['version'],1)
        context='Invoke '+'mcp__claude_ai_Fixture__readPage'+' for fixture context.'
        relative='commands/nightshift-exception-fixture.md'
        (self.source/relative).write_text(context+'\n')
        entry=dict(rule='provider-mcp',path=relative,context=context,reason='Deliberate regression fixture exception for exact context only')
        data['exceptions'].append(entry);policy.write_text(json.dumps(data))
        return policy,data,entry

    def test_exact_exception_and_nearby_unrelated_match(self):
        policy,data,entry=self.policy_exception()
        result,_=self.scan();self.assertEqual(result.returncode,0,result.stdout)
        (self.source/entry['path']).write_text(entry['context']+'\n'+entry['context']+' Additional directive.\n')
        result,payload=self.scan();self.assertEqual(result.returncode,1)
        self.finding(payload,entry['path'],2)

    def test_duplicate_unused_external_and_oversize_policy(self):
        policy,data,entry=self.policy_exception()
        original=json.dumps(data)
        duplicate=json.loads(original);duplicate['exceptions'].append(dict(entry))
        unused=json.loads(original);unused['exceptions'].append(dict(entry,path='commands/nightshift-unused-fixture.md'))
        external=json.loads(original);external['exceptions'].append(dict(entry,path=str(self.forbidden/'private.txt')))
        for content in (json.dumps(duplicate),json.dumps(unused),json.dumps(external),' '* (1024*1024+1)+original):
            with self.subTest(length=len(content)):
                policy.write_text(content);result,_=self.scan();self.assertEqual(result.returncode,64)
        policy.write_text(original)

    def test_installed_exception_uses_exact_source_context(self):
        policy,data,entry=self.policy_exception()
        entries,_=self.installed()
        result,_=self.scan('installed');self.assertEqual(result.returncode,0,result.stdout)
        record=next(e for e in entries if e['source_relative']==entry['path'])
        dest=Path(record['destination']);dest.write_text(entry['context']+' Changed directive.\n')
        result,payload=self.scan('installed');self.assertEqual(result.returncode,1)
        self.finding(payload,record['logical_path'],1)

    def test_source_escape_cycle_encoding_and_oversize(self):
        path=self.source/'docs/nightshift-fixture.md'
        cases=['escape','cycle','encoding','oversize']
        for case in cases:
            with self.subTest(case=case):
                if path.exists() or path.is_symlink():path.unlink()
                if case=='escape':path.symlink_to(self.forbidden/'private.txt')
                elif case=='cycle':path.symlink_to(path.name)
                elif case=='encoding':path.write_bytes(b'\xff\xfe\x80')
                else:path.write_bytes(b'x'*(4*1024*1024+1))
                result,payload=self.scan();self.assertEqual(result.returncode,1);self.assertTrue(payload['coverage'])

    def test_unreadable_source(self):
        path=self.source/'docs/nightshift-unreadable.md';path.write_text('ordinary');path.chmod(0)
        if os.access(path,os.R_OK):self.skipTest('Host identity can read mode-000 fixture')
        result,payload=self.scan();self.assertEqual(result.returncode,1);self.assertTrue(payload['coverage'])

    def test_all_runtime_inventory_and_owned_modes(self):
        for runtime in ('codex','claude','local','all'):
            entries=self.entries(runtime);destinations=[e['destination'] for e in entries]
            self.assertEqual(len(destinations),len(set(destinations)))
            self.assertTrue(any(e['source_relative']=='scripts/nightshift-branding.py' for e in entries))
            self.assertTrue(any(e['source_relative']=='scripts/nightshift-install-inventory.py' for e in entries))
            self.assertTrue(any(e['source_relative']=='scripts/nightshift-branding-policy.json' for e in entries))
            self.assertEqual(any(e['category']=='claude_commands' for e in entries),runtime in ('claude','all'))
            self.assertEqual(any(e['category']=='codex_skill' for e in entries),runtime in ('codex','local','all'))
        self.installed();before=self.snapshot();result,_=self.scan('installed');self.assertEqual(result.returncode,0,result.stdout);self.assertEqual(self.snapshot(),before)

    def test_symlink_install_and_independent_ownership(self):
        entries,_=self.installed('symlink');self.ownership.write_text('{}')
        result,_=self.scan('installed');self.assertEqual(result.returncode,0,result.stdout)
        chosen=next(e for e in entries if e['source_relative']=='agents/nightshift-engineer.md' and e['category']=='shared_roles')
        dest=Path(chosen['destination']);dest.unlink();dest.symlink_to(self.source/'agents/nightshift-architect.md')
        result,payload=self.scan('installed');self.assertEqual(result.returncode,1);self.assertTrue(payload['coverage'])

    def test_owned_copy_drift_and_unknown_copy(self):
        entries,ownership=self.installed()
        chosen=next(e for e in entries if e['source_relative']=='agents/nightshift-engineer.md' and e['category']=='shared_roles')
        dest=Path(chosen['destination']);dest.write_text('ordinary\n'+RETIRED+' '+SECRET+'\n')
        result,payload=self.scan('installed');self.assertEqual(result.returncode,1)
        self.finding(payload,chosen['logical_path'],2)
        ownership.pop(str(dest));self.ownership.write_text(json.dumps(ownership))
        result,payload=self.scan('installed',forbidden=[dest]);self.assertEqual(result.returncode,1);self.assertTrue(payload['coverage'])

    def test_forged_duplicate_and_oversize_ownership(self):
        _,ownership=self.installed()
        forged=dict(ownership);forged[str(self.forbidden/'private.txt')]=str(self.source/'README.md')
        record=json.dumps(ownership);first_key=next(iter(ownership));first_value=ownership[first_key]
        invalid=[json.dumps(forged),'[]','{'+json.dumps(first_key)+':'+json.dumps(first_value)+','+json.dumps(first_key)+':'+json.dumps(first_value)+'}', ' '* (1024*1024+1)+'{}']
        for content in invalid:
            with self.subTest(length=len(content)):
                self.ownership.write_text(content);result,payload=self.scan('installed');self.assertNotEqual(result.returncode,0);self.assertTrue(payload['coverage'] or result.returncode==64)
        self.ownership.write_text(record)

    def test_installed_ancestor_escape_and_unrelated_siblings(self):
        self.installed()
        unrelated=self.targets['claude']/'settings.json';unrelated.write_text(SECRET)
        nested=self.targets['codex']/'skills/unrelated';nested.symlink_to(self.forbidden,target_is_directory=True)
        result,_=self.scan('installed',forbidden=[unrelated]);self.assertEqual(result.returncode,0,result.stdout)
        scripts=self.targets['nightshift']/'scripts';shutil.rmtree(scripts);scripts.symlink_to(self.forbidden,target_is_directory=True)
        result,payload=self.scan('installed',forbidden=[unrelated]);self.assertEqual(result.returncode,1);self.assertTrue(payload['coverage'])

    def test_installed_tree_nested_escape(self):
        entries,ownership=self.installed()
        tree=next(e for e in entries if e['category']=='codex_skill')
        target=Path(tree['destination'])/'nightshift-escape.md'
        target.symlink_to(self.forbidden/'private.txt')
        result,payload=self.scan('installed');self.assertEqual(result.returncode,1);self.assertTrue(payload['coverage'])

    def test_fresh_installer_check_is_json_readonly(self):
        before=self.snapshot()
        binary=self.base/'probe-bin';binary.mkdir()
        calls=self.base/'unexpected-probe'
        for name in ('git','jq','curl','claude','codex','bd','ollama'):
            stub=binary/name;stub.write_text('#!/bin/sh\nprintf probe >> "$PROBE_CALLS"\nexit 99\n');stub.chmod(0o755)
        env=dict(self.env,PATH=str(binary)+os.pathsep+self.env['PATH'],PROBE_CALLS=str(calls))
        before=self.snapshot()
        argv=['bash',str(self.source/'install.sh'),'--check','--runtime','all','--target',str(self.targets['claude']),'--codex-target',str(self.targets['codex']),'--nightshift-target',str(self.targets['nightshift']),'--bin-target',str(self.targets['bin'])]
        result=subprocess.run(argv,env=env,capture_output=True,text=True)
        self.assertFalse(calls.exists(),'Read-only audit invoked dependency/provider probe')
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIsInstance(json.loads(result.stdout),dict)
        self.assertEqual(self.snapshot(),before)

unittest.main(verbosity=2)

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
