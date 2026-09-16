import test from 'node:test';
import assert from 'node:assert/strict';
import { currentRows, filterRows, ticketFailures, evidenceUrl } from './src/model.mjs';
test('ticket blockers retain reasons without confusing factory exit with completion', () => {
  const rows = [
    {ticket:'task-a', source:'gate', state:'blocked', reason:'Write permission denied'},
    {ticket:'task-b', source:'gate', state:'blocked', reason:'Other task'},
    {ticket:'nightshift-factory', source:'agent', state:'success'}
  ];
  assert.deepEqual(ticketFailures(rows, 'task-a').map(r => r.reason), ['Write permission denied']);
});
test('evidence links use the local viewer and reject executable URLs', () => {
  assert.equal(evidenceUrl('file:///tmp/spec.md'), '/evidence?uri=file%3A%2F%2F%2Ftmp%2Fspec.md');
  assert.equal(evidenceUrl('https://example.com/pull/1'), 'https://example.com/pull/1');
  for (const href of ['javascript:alert(1)', 'data:text/html,hello', '//evil.example', 'https://user:pass@example.com']) {
    assert.equal(evidenceUrl(href), null);
  }
});
test('overview preserves concurrent and conflicting source claims', () => {
  const rows = [{ticket:'a',checkout:'one',source:'gate',state:'running',links:[{modified_at:1}]},
    {ticket:'a',checkout:'one',source:'gate',state:'complete',links:[{modified_at:2}]},
    {ticket:'a',checkout:'two',source:'batch',state:'running',provider:'codex'},
    {ticket:'a',checkout:'one',source:'ownership',state:'finished'}];
  assert.equal(currentRows(rows).length, 3);
  assert.equal(currentRows(rows)[0].state, 'complete');
  assert.equal(filterRows(currentRows(rows),'','active','all').length, 2);
  assert.equal(filterRows(currentRows(rows),'a','active','codex').length, 1);
  assert.equal(rows.length,4);
});
