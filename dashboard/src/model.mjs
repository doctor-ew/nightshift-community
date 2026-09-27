export const active = new Set(['running', 'in_progress']);
export const attention = new Set(['blocked', 'failed', 'needs-decision']);
export const modified = row => Math.max(0, ...(row.links || []).filter(Boolean).map(link => link.modified_at || 0));
export function ticketFailures(rows, task) {
  return rows.filter(row => row.ticket === task && row.source === 'gate' && attention.has(row.state))
    .sort((a, b) => modified(b) - modified(a));
}
export function recoveryProgress(ticket) {
  const pipeline=ticket.pipeline, recovery=pipeline?.recovery_status;
  if (!recovery || !['running','blocked','pending_manual_acceptance','complete','awaiting_operator'].includes(recovery.status)) return null;
  const names={verify:'Verification',adoption:'Adoption',review:'Review',drift:'Drift',qa:'QA'};
  const stale=pipeline.status==='stale';
  const next=names[recovery.next_action] || 'Recorded outcome';
  const complete=pipeline.status==='complete' && recovery.status==='complete' && !stale;
  const waiting=recovery.status==='awaiting_operator' && !stale;
  const status=stale ? 'Changed evidence · revalidation required' : complete ? 'Complete' : waiting ? 'Waiting for your decision' : recovery.status==='running' ? `Recovery recorded · ${next}` : recovery.status==='blocked' ? 'Recovery blocked' : recovery.status==='pending_manual_acceptance' ? 'Manual acceptance pending' : 'Recovery completion unconfirmed';
  const calls=recovery.allowance?.calls_used;
  const text=(value,limit=200)=>typeof value==='string' ? value.slice(0,limit) : '';
  const hex=value=>typeof value==='string' && /^[0-9a-f]{64}$/.test(value) ? value : '';
  // Shell-quote anything copied into a command; refs can come from file names.
  const quote=value=>/^[A-Za-z0-9_.:\/#@+-]+$/.test(value) ? value : `'${value.replace(/'/g,`'\\''`)}'`;
  const a=recovery.awaiting;
  const awaiting=waiting && a && typeof a==='object' && hex(a.packet_sha256) && hex(recovery.binding) ? {
    stage:names[a.stage] || text(a.stage,40), question:text(a.packet_id), reason:text(a.reason,120), packet:a.packet_sha256,
    command:`python3 scripts/nightshift-controller-recovery.py operator-decide ${quote(text(ticket.settings?.ref || ticket.task,120))} --expected ${recovery.binding} --packet ${a.packet_sha256} --decision yes|no --reason "<why>" --operator "<you>"`} : null;
  const kinds={};
  for (const call of Object.values(recovery.decision_calls || {})) if (call && typeof call.kind==='string') kinds[call.kind]=(kinds[call.kind] || 0)+1;
  return {status, complete, stale, waiting, awaiting, callKinds:Object.entries(kinds).sort(([x],[y])=>x.localeCompare(y)), recordedRunning:recovery.status==='running',
    reason:typeof recovery.reason==='string' ? recovery.reason.slice(0,2048) : '',
    calls:Number.isSafeInteger(calls) && calls>=0 ? calls : null,
    steps:Object.entries(names).map(([key,label])=>({key,label,status:stale ? 'stale' : ['pass','fail','pending','awaiting_operator'].includes(recovery.steps?.[key]?.status) ? recovery.steps[key].status.replace('awaiting_operator','waiting for your decision') : 'not recorded'})),
    explanation:stale ? 'Recorded recovery evidence changed. Revalidation is required.' : waiting ? 'The independent reviewer could not settle one question. Nothing else is re-asked; decide it, then resume recovery. Waiting time does not use the run allowance.' : recovery.status==='running' ? 'The controller recorded recovery in progress. This record does not verify worker liveness; an interrupted process can leave it unchanged.' : 'Recorded recovery outcome. Original failed attempts remain retained.'};
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
  const dependencyBlocked = ticket.progress?.dependency?.blocked === true;
  const blocker = failures.length > 0 || !!stopped || dependencyBlocked;
  const controlled=ticket.pipeline;
  const recoveryView = recoveryProgress(ticket);
  const status = recoveryView ? recoveryView.status : controlled && !ticket.running ? ({complete:'Complete',pending_manual_acceptance:'Manual acceptance pending',blocked:'Blocked',stale:'Changed evidence · revalidation required',pending:'Ready to resume','needs-decision':'Waiting for your decision'}[controlled.status] || controlled.status) : ticket.running ? (dependencyBlocked ? 'Active · dependency blocked' : 'Running') : blocker && complete ? 'Conflicting outcomes' : blocker ? 'Blocked' : complete ? 'Complete' : ticket.finished ? 'Run ended · outcome unconfirmed' : 'Ready to resume';
  const stage = running || stopped || passed;
  const recovery = controlled?.recovery_status;
  const controlledStage = recovery ? recovery.next_action : controlled?.attempts?.at(-1)?.stage;
  const controlledFailure = controlled?.attempts?.filter(a => a.status === 'fail').at(-1);
  return {trackers, failures, status, tone: recoveryView ? recoveryView.complete ? 'done' : recoveryView.recordedRunning && !recoveryView.stale ? '' : 'warn' : ticket.running ? 'busy' : blocker ? 'warn' : complete ? 'done' : '',
    stoppingReason: recovery ? recovery.reason || '' : controlledFailure?.reason || '',
    stage: controlledStage || stage?.stage || failures[0]?.gate || null,
    stageLabel: recovery ? 'Recovery next step' : controlledStage ? (ticket.running ? 'Current stage' : controlled?.attempts?.at(-1)?.status === 'fail' ? 'Stopped at' : 'Last recorded stage') : ticket.running && !running ? 'Last recorded stage' : blocker ? 'Stopped at' : 'Last recorded stage',
    complete: controlled ? controlled.status === 'complete' : complete && !blocker};
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
  return ['product', 'adversarial', 'implement', 'review', 'drift', 'qa'].map(stage => {
    const completed = ticket.pipeline?.completed?.[stage];
    const attempt = ticket.pipeline?.attempts?.filter(a => a.stage === stage).at(-1);
    if (completed?.recovery_binding && ticket.pipeline?.status !== 'stale') return {stage,state:'passed',detail:'Independently verified recovery receipt; historical failures retained'};
    if (completed?.recovery_binding && ticket.pipeline?.status === 'stale') return {stage,state:'pending',detail:'Recovery evidence changed; revalidation required'};
    if (attempt && attempt.status !== 'pass') return {stage, state: attempt.status === 'fail' ? 'failed' : 'running', detail: attempt.reason || 'Controller attempt in progress'};
    if (completed) return {stage, state: 'passed', detail: 'Controller retained completed-stage receipt'};
    if (ticket.pipeline) return {stage, state:'pending', detail:'No controller stage evidence recorded yet'};
    return recorded.find(step => step.stage === stage) || {stage, state:'pending', detail:'No stage evidence recorded yet'};
  });
}
export function ticketUsage(reports, ticket) {
  return reports.filter(report => report.ticket?.source_id === ticket.task);
}


export function continuationControl(ticket) {
  const budget = ticket.budget;
  let reason = '';
  if (!budget || budget.error || !budget.revision) reason = 'Budget accounting is unavailable.';
  else if (ticket.running || budget.unfinished > 0) reason = 'Wait for active work to finish.';
  else if (ticket.finished || ['complete', 'pending_manual_acceptance'].includes(ticket.pipeline?.status) || ticket.recovery?.next_action === 'operator_verify_manual_acceptance') reason = 'Review the recorded outcome; more runtime is not needed.';
  else if (ticket.decisions?.pending?.length) reason = 'Answer the pending decision first.';
  else if (stageRetriesExhausted(ticket)) reason = 'Stage retry limit reached. More time cannot add retries; explicit recovery is needed.';
  else if (budget.calls_reserved >= budget.max_calls) reason = 'Launch limit reached. More time cannot add launches.';
  else if (!budget.exhausted && budget.wall_seconds_remaining != null) reason = 'Time remains. Use Resume without granting a new allowance.';
  return {disabled: !!reason, reason};
}

export function workerDiagnostic(ticket) {
  const diagnostic = ticket.pipeline?.attempts?.at(-1)?.diagnostic;
  if (diagnostic?.label !== 'UNVALIDATED_WORKER_DIAGNOSTIC') return null;
  const text = value => typeof value === 'string' ? value.slice(0, 1024) : '';
  return {
    validationError: text(diagnostic.validation_error),
    findings: (Array.isArray(diagnostic.reported_findings) ? diagnostic.reported_findings : []).slice(0, 3)
      .map(row => ({target:text(row?.target),problem:text(row?.problem)})).filter(row => row.problem),
    path: text(diagnostic.path), sha256: text(diagnostic.sha256),
  };
}

export function stageRetriesExhausted(ticket) {
  return !!ticket.retry_exhausted_stage || ticket.pipeline?.retry_budgets?.[ticket.pipeline?.next_action]?.next_action === 'stop';
}
