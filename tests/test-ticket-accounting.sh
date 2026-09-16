#!/usr/bin/env bash
# Behavioral contract for issue 35. Run: bash tests/test-ticket-accounting.sh
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 - "$ROOT" <<'PY'
import copy, hashlib, json, os, pathlib, subprocess, sys, tempfile, unittest

ROOT = pathlib.Path(sys.argv.pop())
METRICS = ROOT / 'scripts/nightshift-run-metrics.py'
PARSER = ROOT / 'scripts/nightshift-provider-usage.py'
TICKET = {'source': 'gh', 'repository': 'fixture/accounting', 'source_id': '35'}
SECRET = 'SECRET_ACCOUNTING_FIXTURE_35'
PROMPT = 'PRIVATE PROMPT ACCOUNTING FIXTURE 35'

class Accounting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='nightshift-ticket-contract-')
        self.addCleanup(self.tmp.cleanup)
        self.project = pathlib.Path(self.tmp.name)
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', GH_TOKEN=SECRET)
        for key in ('NIGHTSHIFT_RUN_ID', 'NIGHTSHIFT_RUN_DIR', 'NIGHTSHIFT_PROJECT_DIR'):
            self.env.pop(key, None)
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        self.contexts = []

    def cli(self, *args):
        return subprocess.run([sys.executable, str(METRICS), *map(str, args)],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def run_context(self):
        result = self.cli('init', '--project', self.project, '--branch', 'none')
        self.assertEqual(result.returncode, 0)
        context = json.loads(result.stdout)
        self.assertTrue(context['metrics_available'])
        self.contexts.append(context)
        return context

    def receipt(self, context, invocation='main', tokens=10, ticket=None, **changes):
        value = dict(schema_version=2, ticket=copy.deepcopy(ticket or TICKET), attribution='ticket',
                     run_id=context['run_id'], invocation_id=invocation, receipt_id='result',
                     sequence=0, stream_epoch='0', provider='claude', selected_model='sonnet',
                     reported_model='fixture-reported-model', stage='implement', status='success',
                     role='orchestrator', coverage_scope='self', parent_invocation_id=None,
                     included_invocation_ids=[], child_kind='none',
                     usage=dict(fresh_input=tokens, cache_read_input=0, cache_write_input=0,
                                output=2, reasoning_output=None, total=tokens+2),
                     cost=dict(provider_reported_estimate_usd=0.01, token_derived_estimate_usd=None,
                               actual_billed_usd=None, pricing_sources=[]))
        value.update(changes)
        return value

    def ingest(self, context, value):
        path = self.project / 'receipt-input.json'
        path.write_text(json.dumps(value))
        result = self.cli('ingest', '--run-dir', context['run_dir'], '--receipt-file', path)
        self.assertEqual(result.returncode, 0, 'C35: normalized accounting receipt must be accepted')
        return result

    def report(self, ticket=None):
        ticket = ticket or TICKET
        result = self.cli('ticket-report', '--project', self.project, '--source', ticket['source'],
                          '--repository', ticket['repository'], '--source-id', ticket['source_id'])
        self.assertEqual(result.returncode, 0, 'C35: persisted ticket report must be available')
        self.assertTrue(result.stdout.strip(), 'C35: report must be machine-readable JSON')
        return json.loads(result.stdout)

    def total(self, report):
        return report['usage']['known_subtotal']['total']

    def home(self):
        identity = [TICKET[k] for k in ('source', 'repository', 'source_id')]
        key = hashlib.sha256(json.dumps(identity, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        return self.project / '.git/nightshift/ticket-metrics' / key

    def parse(self, provider, events):
        self.assertTrue(PARSER.is_file(), 'C35: structured provider usage adapter is required')
        path = self.project / 'provider.jsonl'
        path.write_text('\n'.join(json.dumps(event) for event in events)+'\n')
        result = subprocess.run([sys.executable, str(PARSER), '--provider', provider, '--input', str(path)],
                                env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0)
        parsed = json.loads(result.stdout)
        self.assertIsInstance(parsed, list)
        self.assertTrue(parsed, 'C35: available structured usage was discarded')
        return parsed

    def test_C35_1_ticket_isolation_and_failed_attempts(self):
        first, second = self.run_context(), self.run_context()
        self.ingest(first, self.receipt(first, tokens=10))
        self.ingest(second, self.receipt(second, tokens=20, status='failed'))
        for ticket in (dict(TICKET, repository='fixture/other'), dict(TICKET, source_id='36')):
            other = self.run_context()
            self.ingest(other, self.receipt(other, tokens=900, ticket=ticket))
        report = self.report()
        self.assertEqual(report['ticket'], TICKET)
        self.assertEqual(report['run_count'], 2)
        self.assertEqual(self.total(report), 34)
        self.assertTrue(any(run['status'] == 'failed' for run in report['runs']))

    def test_C35_2_replay_cumulative_conflict(self):
        context = self.run_context()
        first = self.receipt(context, tokens=10)
        self.ingest(context, first)
        self.ingest(context, first)
        self.assertEqual(self.total(self.report()), 12)
        later = self.receipt(context, tokens=30, sequence=1)
        self.ingest(context, later)
        self.ingest(context, first)
        self.assertEqual(self.total(self.report()), 32)
        self.assertEqual(self.total(self.report()), 32)
        conflicting = self.receipt(context, tokens=99, sequence=1)
        self.ingest(context, conflicting)
        report = self.report()
        self.assertGreater(report['completeness']['conflict_count'], 0)
        self.assertFalse(report['usage']['complete'])
        self.assertNotIn(self.total(report), (32, 101, 133))

    def test_C35_3_overlap_and_provider_cache_categories(self):
        context = self.run_context()
        self.ingest(context, self.receipt(context, 'parent', tokens=100, coverage_scope='inclusive',
                                         included_invocation_ids=['child']))
        self.ingest(context, self.receipt(context, 'child', tokens=40, role='nightshift-engineer',
                                         parent_invocation_id='parent', child_kind='sdk_internal'))
        self.assertEqual(self.total(self.report()), 102)
        # Unknown inclusion is distinct from an explicitly empty inclusion list.
        other = self.run_context()
        self.ingest(other, self.receipt(other, 'uncertain-parent', tokens=20,
                                        coverage_scope='inclusive', included_invocation_ids=None))
        self.ingest(other, self.receipt(other, 'external', tokens=7, role='nightshift-engineer',
                                        parent_invocation_id='uncertain-parent', child_kind='external_dispatch'))
        report = self.report()
        self.assertGreater(report['completeness']['overlap_unknown_count'], 0)
        self.assertFalse(report['usage']['complete'])
        self.assertIsNotNone(report['usage']['nonadditive_observed'])
        parsed = self.parse('codex', [dict(type='thread.started', thread_id='fixture-thread'),
            dict(type='turn.completed', usage=dict(input_tokens=100, cached_input_tokens=40,
                cache_write_input_tokens=60, output_tokens=10, reasoning_output_tokens=5))])
        usage = parsed[-1]['usage']
        self.assertEqual([usage[k] for k in ('fresh_input','cache_read_input','cache_write_input','output','total')],
                         [0,40,60,10,110])
        self.assertIsNone(parsed[-1].get('reported_model'))

    def test_C35_4_partial_usage_model_and_pricing(self):
        context = self.run_context()
        self.ingest(context, self.receipt(context, tokens=10))
        self.ingest(context, self.receipt(context, 'missing', usage=None, reported_model=None,
                                         role='nightshift-engineer', cost=None))
        report = self.report()
        self.assertEqual(self.total(report), 12)
        for key in ('missing_usage_count','missing_model_count','missing_pricing_count'):
            self.assertGreater(report['completeness'][key], 0)
        self.assertFalse(report['usage']['complete'])
        self.assertFalse(report['cost']['complete'])
        self.assertAlmostEqual(report['cost']['provider_reported_estimate_usd'], 0.01)
        self.assertIsNone(report['cost']['token_derived_estimate_usd'])
        self.assertIsNone(report['cost']['actual_billed_usd'])

    def test_C35_5_orchestrator_measured_and_unmeasured(self):
        measured, absent = self.run_context(), self.run_context()
        self.ingest(measured, self.receipt(measured, tokens=50))
        self.ingest(absent, self.receipt(absent, 'child', tokens=10, role='nightshift-engineer'))
        report = self.report()
        self.assertEqual(self.total(report), 64)
        self.assertGreater(report['completeness']['unmeasured_orchestrator_count'], 0)
        self.assertFalse(report['usage']['complete'])

    def test_C35_6_restart_and_stale_atomic_summary(self):
        context = self.run_context()
        self.ingest(context, self.receipt(context, tokens=10))
        summary = self.home()/'summary.json'
        self.assertTrue(summary.is_file(), 'C35: ticket summary must persist on ingestion')
        before = summary.read_bytes()
        self.ingest(context, self.receipt(context, 'after-summary', tokens=20, status='interrupted'))
        summary.write_bytes(before)  # Simulate a crash with an old cache and newer durable receipts.
        report = self.report()       # Each CLI invocation is a new process.
        self.assertEqual(self.total(report), 34)
        self.assertEqual(self.total(json.loads(summary.read_text())), 34)
        self.assertGreaterEqual(report['provenance']['receipt_count'], 2)
        self.assertTrue(any(run['status'] == 'interrupted' for run in report['runs']))

    def test_C35_7_breakdowns_match_same_additive_set(self):
        context = self.run_context()
        self.ingest(context, self.receipt(context, tokens=10, stage='qa'))
        self.ingest(context, self.receipt(context, 'unknown', tokens=20, stage=None,
                                         provider='codex', reported_model=None))
        report = self.report()
        self.assertIn('qa', report['breakdowns']['stage'])
        self.assertIn('unknown', report['breakdowns']['stage'])
        for axis in ('stage','provider','reported_model'):
            buckets = report['breakdowns'][axis].values()
            total = sum(b.get('known_subtotal', b).get('total') or 0 for b in buckets)
            self.assertEqual(total, self.total(report))

    def test_C35_8_provider_errors_privacy_and_io(self):
        # Real documented Claude result shape; the second result is cumulative, not additive.
        events = []
        for n in (10, 20):
            events.append(dict(type='result', subtype='success' if n==10 else 'error_max_turns',
                is_error=n==20, session_id='fixture-session', total_cost_usd=n/1000,
                usage=dict(input_tokens=n, cache_read_input_tokens=4, cache_creation_input_tokens=2, output_tokens=3),
                modelUsage={'fixture-reported-model': dict(inputTokens=n,cacheReadInputTokens=4,
                    cacheCreationInputTokens=2,outputTokens=3,costUSD=n/1000)}, result=PROMPT))
        parsed = self.parse('claude', events)
        last = parsed[-1]
        self.assertEqual(last['usage']['total'], 29)
        self.assertAlmostEqual(last['cost']['provider_reported_estimate_usd'], 0.02)
        self.assertIsNone(last['cost'].get('actual_billed_usd'))
        self.assertTrue(last['cost']['pricing_sources'], 'C35: reported estimate requires source provenance')
        self.assertNotIn(PROMPT, json.dumps(parsed))
        context = self.run_context()
        value = self.receipt(context, prompt=PROMPT, credential=SECRET)
        self.ingest(context, value)
        malformed = self.project/'malformed.json'
        malformed.write_text('not-json '+SECRET+' '+PROMPT)
        bad = self.cli('ingest','--run-dir',context['run_dir'],'--receipt-file',malformed)
        self.assertEqual(bad.returncode, 0, 'C35: accounting parse failures must be non-gating')
        missing = self.cli('ingest','--run-dir',context['run_dir'],'--receipt-file',self.project/'missing.json')
        self.assertEqual(missing.returncode, 0)
        invalid_receipt = self.home()/'receipts/corrupt.json'
        invalid_receipt.write_text('broken '+SECRET+' '+PROMPT)
        report = self.report()
        self.assertGreater(report['completeness']['read_error_count'], 0)
        self.assertEqual(self.total(report), 12)
        for text in (bad.stdout,bad.stderr,missing.stdout,missing.stderr,json.dumps(report)):
            self.assertNotIn(SECRET,text); self.assertNotIn(PROMPT,text)
        # Preserve every retained receipt while making only summary publication unavailable.
        summary = self.home()/'summary.json'
        summary.rename(self.home()/'retained-summary.json')
        summary.mkdir()
        response = self.ingest(context,self.receipt(context,'write-failure',tokens=1))
        self.assertEqual(response.returncode,0)
        for path in self.home().rglob('*.json'):
            if path.is_file() and path != invalid_receipt:
                text=path.read_text();self.assertNotIn(SECRET,text);self.assertNotIn(PROMPT,text)

unittest.main(verbosity=2)
PY
