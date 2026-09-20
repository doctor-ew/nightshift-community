export const active = new Set(['running', 'in_progress']);
export const attention = new Set(['blocked', 'failed', 'needs-decision']);
export const modified = row => Math.max(0, ...(row.links || []).filter(Boolean).map(link => link.modified_at || 0));
export function ticketFailures(rows, task) {
  return rows.filter(row => row.ticket === task && row.source === 'gate' && attention.has(row.state))
    .sort((a, b) => modified(b) - modified(a));
}
export function ticketProgress(rows, ticket) {
  const related = rows.filter(row => row.ticket === ticket.task);
  const trackers = related.filter(row => row.pipeline_steps?.length);
  const failures = ticketFailures(rows, ticket.task);
  const complete = related.some(row => row.source === 'batch' && row.state === 'complete');
  const steps = trackers.flatMap(row => row.pipeline_steps);
  const stopped = steps.find(step => ['blocked', 'failed'].includes(step.state));
  const running = steps.find(step => step.state === 'running');
  const passed = steps.filter(step => step.state === 'passed').at(-1);
  const blocker = failures.length > 0 || !!stopped;
  const status = ticket.running ? 'Running' : blocker && complete ? 'Conflicting outcomes' : blocker ? 'Blocked' : complete ? 'Complete' : ticket.finished ? 'Run ended · outcome unconfirmed' : 'Ready to resume';
  const stage = running || stopped || passed;
  return {trackers, failures, status, tone: ticket.running ? 'busy' : blocker ? 'warn' : complete ? 'done' : '',
    stage: stage?.stage || failures[0]?.gate || null,
    stageLabel: ticket.running && !running ? 'Last recorded stage' : blocker ? 'Stopped at' : 'Last recorded stage',
    complete: complete && !blocker};
}
export function blockerSummary(reason = '') {
  const field = label => reason.split(/\n(?=- )/).find(part => part.startsWith('- ' + label + ':'))?.slice(label.length + 3).trim();
  return {reason: field('Root cause') || reason, next: field('Unblock path') || 'Resolve the blocker before resuming. Retrying unchanged may fail again.'};
}
export function ticketSourceLink(rows, ticket) {
  const related = rows.filter(row => row.ticket === ticket.task);
  const ref = ticket.settings?.ref || '';
  for (const href of [...related.map(row => row.ticket_url), ref]) {
    if (typeof href === 'string' && /^https?:\/\//.test(href) && evidenceUrl(href)) return {href, label: 'Open ticket'};
  }
  const links = related.flatMap(row => row.links || []).filter(Boolean);
  const local = ref.replace(/^spec:/, '');
  const source = local && links.find(link => {
    try { return decodeURIComponent(new URL(link.href).pathname).endsWith('/' + local); } catch { return false; }
  });
  if (source) return {...source, label: 'Open source'};
  const tracker = links.find(link => link.label === ticket.task + '.md');
  return tracker ? {...tracker, label: 'Open local record'} : null;
}
export function evidenceUrl(href) {
  if (typeof href !== 'string') return null;
  if (href.startsWith('file:///')) return '/evidence?uri=' + encodeURIComponent(href);
  try {
    const url = new URL(href);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}
export function currentRows(rows) {
  // File mtime orders presentation only. Never use it to supersede another gate,
  // batch or attempt's claim; concurrent and contradictory evidence stays visible.
  return rows.filter(r => ['batch', 'gate'].includes(r.source))
    .sort((a, b) => modified(b) - modified(a));
}
export function filterRows(rows, query, state, provider) {
  return rows.filter(row => (!query || [row.ticket, row.gate, row.checkout, row.provider].join(' ').toLowerCase().includes(query.toLowerCase()))
    && (state === 'all' || (state === 'active' ? active.has(row.state) : state === 'attention' ? attention.has(row.state) : row.state === state))
    && (provider === 'all' || row.provider === provider));
}

// Planned stages are visible before any tracker exists; no success is inferred.
export function ticketTimeline(rows, ticket) {
  const recorded = rows.filter(row => row.ticket === ticket.task).flatMap(row => row.pipeline_steps || []);
  return ['product', 'adversarial', 'implement', 'review', 'drift', 'qa'].map(stage =>
    recorded.find(step => step.stage === stage) || {stage, state:'pending', detail:'No stage evidence recorded yet'});
}
export function ticketUsage(reports, ticket) {
  return reports.filter(report => report.ticket?.source_id === ticket.task);
}
