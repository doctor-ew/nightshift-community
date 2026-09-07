import test from 'node:test';
import assert from 'node:assert/strict';
import { currentRows, filterRows } from './src/model.mjs';
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
