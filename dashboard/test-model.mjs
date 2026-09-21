import test from 'node:test';
import assert from 'node:assert/strict';
import { currentRows, filterRows, ticketFailures, evidenceUrl, ticketProgress, blockerSummary, ticketSourceLink, ticketTimeline, ticketUsage } from './src/model.mjs';
test('parent dependency blockage remains explicit even while orchestrator exits or runs', () => {
  const ticket = {task:'parent', finished:true, progress:{dependency:{blocked:true}}};
  assert.equal(ticketProgress([], ticket).status, 'Blocked');
  assert.equal(ticketProgress([], {...ticket,running:true}).status, 'Active · dependency blocked');
  assert.equal(ticketProgress([{ticket:'parent',source:'batch',state:'complete'}],ticket).complete,false);
});
test('ticket source links preserve recorded external URLs and local evidence', () => {
  const ticket = {task:'task-a', settings:{ref:'jira:task-a'}};
  const rows = [{ticket:'task-a', ticket_url:'https://example.atlassian.net/browse/task-a', links:[{label:'task-a.md',href:'file:///tmp/task-a.md'}]}];
  assert.equal(ticketSourceLink(rows, ticket).href, rows[0].ticket_url);
  rows[0].ticket_url = 'https://github.com/example/project/issues/12';
  assert.equal(ticketSourceLink(rows, ticket).label, 'Open ticket');
  rows[0].ticket_url = 'javascript:alert(1)';
  assert.equal(ticketSourceLink(rows, ticket).label, 'Open local record');
  ticket.settings.ref = 'spec:task-a.md';
  assert.equal(ticketSourceLink(rows, ticket).label, 'Open source');
  assert.equal(ticketSourceLink([], {task:'missing'}), null);
});
test('blocker card preserves multiline reason and offers the recorded unblock action', () => {
  const result = blockerSummary('- Stage: implement\n- Root cause: Name unresolved\n  in prerequisite.\n- Unblock path: Record a naming decision.\n- Other: retained evidence');
  assert.equal(result.reason, 'Name unresolved\n  in prerequisite.');
  assert.equal(result.next, 'Record a naming decision.');
  assert.equal(blockerSummary('Permission denied').reason, 'Permission denied');
});
test('timeline does not turn process exit or finished ownership into completion', () => {
  const rows = [{ticket:'task-a', source:'artifacts', pipeline_steps:[
    {stage:'product', state:'passed'}, {stage:'implement', state:'blocked'}, {stage:'review', state:'pending'}
  ]}, {ticket:'task-a', source:'ownership', state:'finished'}, {ticket:'nightshift-factory', source:'agent', state:'success'}];
  const ended = ticketProgress(rows, {task:'task-a', finished:true});
  assert.equal(ended.status, 'Blocked');
  assert.equal(ended.stage, 'implement');
  assert.equal(ended.complete, false);
  const resumed = ticketProgress(rows, {task:'task-a', running:true});
  assert.equal(resumed.status, 'Running');
  assert.equal(resumed.stageLabel, 'Last recorded stage');
});
test('completion requires delivery evidence and conflicting failures remain visible', () => {
  const ticket = {task:'task-a', finished:true};
  assert.equal(ticketProgress([], ticket).status, 'Run ended · outcome unconfirmed');
  const rows = [{ticket:'task-a', source:'batch', state:'complete'}];
  assert.equal(ticketProgress(rows, ticket).complete, true);
  rows.push({ticket:'task-a', source:'gate', state:'blocked', reason:'Retained failure'});
  assert.equal(ticketProgress(rows, ticket).status, 'Conflicting outcomes');
  assert.equal(ticketProgress(rows, ticket).complete, false);
});
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

test('fresh tickets show the full planned timeline without claiming passed gates', () => {
  const ticket = {task:'fresh', running:true};
  assert.equal(ticketTimeline([], ticket).length, 6);
  assert.ok(ticketTimeline([], ticket).every(step => step.state === 'pending'));
  const steps = ticketTimeline([{ticket:'old',pipeline_steps:[{stage:'qa',state:'passed'}]}, {ticket:'fresh',pipeline_steps:[{stage:'product',state:'running'}]}], ticket);
  assert.equal(steps[0].state, 'running');
  assert.equal(steps[5].state, 'pending');
});
test('ticket usage never borrows totals from the previous build', () => {
  const old = {ticket:{source_id:'old'},usage:{known_subtotal:{total:900}}};
  assert.deepEqual(ticketUsage([old], {task:'fresh'}), []);
  const fresh = {ticket:{source_id:'fresh'},usage:{known_subtotal:{total:12}}};
  assert.deepEqual(ticketUsage([old,fresh], {task:'fresh'}), [fresh]);
});
