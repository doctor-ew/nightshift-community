import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { active, attention, currentRows, filterRows, modified, ticketFailures, evidenceUrl } from './model.mjs';
import './app.css';

function WorkshopReviews() {
  const [items, setItems] = useState([]), [token, setToken] = useState(''), [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  useEffect(() => {
    let disposed = false;
    const refresh = async () => {
      try {
        const response = await fetch('/api/workshop/reviews', { cache: 'no-store' });
        if (!response.ok) throw new Error('Spec reviews unavailable. Refresh or check the terminal.');
        const data = await response.json();
        if (!disposed) { setItems(data.reviews.map(i => ({ ...i, started: i.launch?.status === 'running' }))); setToken(data.token); setError(''); }
      } catch (e) { if (!disposed) setError(e.message); }
    };
    refresh(); const timer = setInterval(refresh, 3000);
    return () => { disposed = true; clearInterval(timer); };
  }, []);
  async function approve(item) {
    setBusy(item.task); setError('');
    try {
      const response = await fetch('/api/workshop/approve', { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Nightshift-Token': token },
        body: JSON.stringify({ task: item.task, sha256: item.sha256 }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Approval failed. Reload the spec.');
      setItems(current => current.map(i => i.task === item.task ? { ...i, approved: true, started: true } : i));
    } catch (e) { setError(e.message); }
    finally { setBusy(''); }
  }
  if (!items.length && !error) return null;
  return <section className="workspace" aria-label="Spec approvals"><h2>Review your spec</h2>
    {error && <p role="alert">{error}</p>}
    {items.map(item => <article className="run" key={item.task}><h3>{item.task}</h3>
      {item.error ? <p role="alert">{item.error}</p> : <>
        <p>Also saved in your project: <code>{item.copy_path}</code></p>
        <pre className="spec-preview">{item.spec}</pre>
        {item.launch?.status === 'exited' && item.launch.exit_code !== 0 && <p role="alert">Build startup failed. See the retained log: {item.launch.log}</p>}
        <p>Read the requirements and exclusions before approving this version.</p>
        <button disabled={!!busy || item.started} onClick={() => approve(item)}>{item.started ? 'Build started' : busy === item.task ? 'Starting…' : item.approved ? 'Continue approved build' : 'Approve and build'}</button>
        {item.approved && <p role="status">{item.started ? 'Build started. Follow its progress in Run overview below.' : 'This spec is approved. Click Continue approved build to resume.'}</p>}
      </>}
    </article>)}
  </section>;
}

function EvidenceLink({ link }) {
  const href = evidenceUrl(link?.href);
  return href ? <a href={href} target="_blank" rel="noopener noreferrer">{link.label || 'Open evidence'} ↗</a> : null;
}

function EvidenceViewer() {
  const uri = new URLSearchParams(window.location.search).get('uri') || '';
  const [content, setContent] = useState(null), [error, setError] = useState(''), [copied, setCopied] = useState(false);
  let name = 'Evidence';
  try { name = decodeURIComponent(new URL(uri).pathname.split('/').pop()); } catch {}
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/evidence?uri=' + encodeURIComponent(uri), {signal: controller.signal})
      .then(async response => { if (!response.ok) throw new Error(await response.text()); return response.text(); })
      .then(setContent).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, [uri]);
  const download = () => {
    const url = URL.createObjectURL(new Blob([content], {type: 'text/plain;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = name; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  let displayed = content;
  if (name.endsWith('.json') && content !== null) { try { displayed = JSON.stringify(JSON.parse(content), null, 2); } catch {} }
  return <main><header><div className="brand">nightshift · Evidence</div><a href="/">Back to tickets</a></header>
    <section className="workspace"><h1>{name}</h1><p className="repo">{uri}</p>
      {error ? <p role="alert">{error}</p> : content === null ? <p>Loading evidence…</p> : <>
        <div className="artifact-actions"><button className="secondary" onClick={download}>Download file</button><button className="secondary" onClick={async () => { try { await navigator.clipboard.writeText(content); setCopied(true); } catch { setError('Clipboard unavailable. Select the text or download the file.'); } }}>{copied ? 'Copied' : 'Copy contents'}</button></div>
        <pre className="evidence-document">{displayed}</pre>
      </>}
    </section></main>;
}

function ArtifactLibrary({ rows }) {
  const [query, setQuery] = useState('');
  const files = new Map();
  for (const row of rows) for (const link of row.links || []) {
    if (link && evidenceUrl(link.href)) files.set(link.href, {...link, ticket: row.ticket});
  }
  const shown = [...files.values()].filter(link => [link.label, link.ticket, link.href].join(' ').toLowerCase().includes(query.toLowerCase()));
  return <section className="workspace" aria-label="Specs and artifacts"><h2>Specs and artifacts</h2>
    <p>Open any collected file in a new tab to read, copy, or download it.</p>
    <div className="filters"><label className="search">Find a file<input value={query} onChange={e => setQuery(e.target.value)} placeholder="Ticket, spec, review, tests, receipt…" /></label></div>
    <div className="artifact-library">{shown.map(link => <div className="artifact-row" key={link.href}><span>{link.ticket}</span><EvidenceLink link={link} /></div>)}</div>
    {!shown.length && <p>{files.size ? 'No matching files.' : 'Files will appear as the run creates them.'}</p>}
  </section>;
}

function TicketActions({ rows }) {
  const [data, setData] = useState({ tickets: [] }), [busy, setBusy] = useState(''), [message, setMessage] = useState('');
  useEffect(() => {
    let disposed = false;
    async function refresh() {
      try {
        const response = await fetch('/api/tickets', { cache: 'no-store' });
        if (!response.ok) throw new Error('Ticket actions unavailable. Restart the console to load its latest version.');
        const value = await response.json();
        if (!disposed) setData(value);
      } catch (error) { if (!disposed) setMessage(error.message); }
    }
    refresh(); const timer = setInterval(refresh, 3000);
    return () => { disposed = true; clearInterval(timer); };
  }, []);
  async function act(ticket, operation) {
    setBusy(ticket.task); setMessage('');
    try {
      const response = await fetch('/api/tickets/' + operation, { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Nightshift-Token': data.token },
        body: JSON.stringify({ task: ticket.task, sha256: ticket.sha256 }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Could not continue this ticket.');
      setMessage(ticket.task + ': ' + result.message);
      if (result.status === 'running') setData(current => ({ ...current, tickets: current.tickets.map(t => t.task === ticket.task ? { ...t, running: true } : t) }));
    } catch (error) { setMessage(error.message); }
    finally { setBusy(''); }
  }
  if (!data.tickets.length && !message) return null;
  return <section className="workspace" aria-label="Ticket status"><h2>Tickets</h2>
    <p>Resume preserves existing work and checks for live workers before starting. Clean up prepares the ticket without starting a model.</p>
    {message && <p role="status">{message}</p>}
    <div className="cards">{data.tickets.map(ticket => {
      const failures = ticketFailures(rows, ticket.task);
      const blocked = !ticket.running && failures.length > 0;
      const artifacts = rows.filter(row => row.ticket === ticket.task && row.source === 'artifacts').flatMap(row => row.links || []).filter(Boolean);
      const specs = artifacts.filter(link => link.label === 'SPEC.md');
      const prs = [...new Set(rows.filter(row => row.ticket === ticket.task).map(row => row.pr_url_text).filter(Boolean))];
      return <article className="run" key={ticket.task}>
      <div className="run-head"><h3>{ticket.task}</h3><span className={'badge ' + (blocked ? 'warn' : ticket.running ? 'busy' : '')}>{ticket.running ? 'Running' : blocked ? 'Blocked · failure recorded' : ticket.finished ? 'Run ended' : 'Ready to resume'}</span></div>
      {blocked && <div className="failure-summary" role="status"><h4>Stopped at {failures[0].gate}</h4><p>{failures[0].reason}</p><p>Resolve the blocker before resuming. Retrying unchanged may fail again.</p>{failures[0].links?.filter(Boolean).map((link, i) => <EvidenceLink key={i} link={link} />)}</div>}
      <p>{ticket.settings.provider} · {ticket.settings.policy} · {ticket.settings.auth}</p>
      <p>{ticket.settings.push ? (ticket.settings.pr ? 'Push and open PR after verification' : 'Push after verification') : 'Keep results local'}</p>
      <div className="artifact-actions">{specs.map((link, i) => <EvidenceLink key={i} link={{...link, label: 'Open spec'}} />)}{prs.map(href => <EvidenceLink key={href} link={{href, label: 'Open pull request'}} />)}</div>
      {ticket.launch?.status === 'exited' && ticket.launch.exit_code !== 0 && <p>Last launch exited with code {ticket.launch.exit_code}. Log: <code>{ticket.launch.log}</code></p>}
      <div className="run-footer"><button disabled={!!busy || ticket.running || ticket.finished} onClick={() => act(ticket, 'resume')}>{ticket.finished ? 'Run ended' : ticket.running ? 'Running' : busy === ticket.task ? 'Working…' : 'Resume'}</button>
      <button className="secondary" disabled={!!busy || ticket.running || ticket.finished} onClick={() => act(ticket, 'cleanup')}>Clean up</button></div>
      {!!artifacts.length && <details><summary>Files and evidence ({artifacts.length})</summary>{artifacts.map((link, i) => <div className="evidence" key={i}><EvidenceLink link={link} /></div>)}</details>}
    </article>;})}</div>
  </section>;
}

function TicketUsage({ reports = [] }) {
  const number = value => typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString() : 'Unknown';
  const money = value => typeof value === 'number' && Number.isFinite(value) ? '$' + value.toFixed(6) : 'Unknown';
  return <section className="workspace" aria-label="Ticket usage"><h2>Ticket cost and tokens</h2>
    <p>Known totals across runs and retries. Provider estimates are not subscription charges. Usage updates when each worker finishes.</p>
    {!reports.length && <div className="empty"><h3>No usage recorded yet</h3><p>Earlier runs may have no accounting receipts. Missing usage and prices are unknown, not zero.</p></div>}
    <div className="cards">{reports.map((r, i) => <article className="run" key={i}>
      <div className="run-head"><h3>{r.ticket?.source}:{r.ticket?.source_id}</h3><span className={'badge ' + (r.usage?.complete ? 'done' : 'warn')}>{r.usage?.complete ? 'Tokens complete' : 'Partial usage'}</span></div>
      <p>{r.ticket?.repository} · {number(r.run_count)} runs</p>
      <p><strong>Tokens: {number(r.usage?.known_subtotal?.total)}</strong></p>
      <p><strong>Provider estimate: {money(r.cost?.provider_reported_estimate_usd)} USD</strong></p>
      <p>Token-priced estimate: {money(r.cost?.token_derived_estimate_usd)} USD · Actual billed: {money(r.cost?.actual_billed_usd)} USD</p>
      <details><summary>Token categories and stage breakdown</summary>
        <p>Fresh input: {number(r.usage?.known_subtotal?.fresh_input)} · Cache read: {number(r.usage?.known_subtotal?.cache_read_input)} · Cache write: {number(r.usage?.known_subtotal?.cache_write_input)} · Output: {number(r.usage?.known_subtotal?.output)}</p>
        {Object.entries(r.breakdowns?.stage || {}).map(([stage, values]) => <p key={stage}>{stage}: {number(values.known_subtotal?.total)} tokens · {money(values.cost?.provider_reported_estimate_usd)} USD estimate</p>)}
        <p>Unmeasured orchestrators: {number(r.completeness?.unmeasured_orchestrator_count)} · Uncertain overlaps: {number(r.completeness?.overlap_unknown_count)}</p>
      </details>
    </article>)}</div>
  </section>;
}

function App() {
  const [data, setData] = useState(null), [error, setError] = useState('');
  const [query, setQuery] = useState(''), [state, setState] = useState('all'), [provider, setProvider] = useState('all');
  const [history, setHistory] = useState(false), [page, setPage] = useState(0);
  const [agentState, setAgentState] = useState('all'), [agentPage, setAgentPage] = useState(0);
  useEffect(() => {
    let disposed = false, timer;
    const controller = new AbortController();
    async function refresh() {
      try {
        const response = await fetch('/api/state', { signal: controller.signal, cache: 'no-store' });
        if (!response.ok) throw new Error('Collection unavailable. Retaining the last snapshot and retrying.');
        const snapshot = await response.json();
        if (!disposed) { setData(snapshot); setError(''); }
      } catch (e) { if (!disposed) setError(e.message); }
      if (!disposed) timer = setTimeout(refresh, 3000);
    }
    refresh();
    return () => { disposed = true; clearTimeout(timer); controller.abort(); };
  }, []);
  const rows = data?.rows || [];
  const current = useMemo(() => currentRows(rows), [rows]);
  const agents = rows.filter(r => r.source === 'agent').sort((a,b)=>modified(b)-modified(a));
  const filteredAgents = agents.filter(r=>agentState==='all' || r.state===agentState);
  const agentPages = Math.max(1,Math.ceil(filteredAgents.length/12));
  const safeAgentPage = Math.min(agentPage,agentPages-1);
  const shown = filterRows(history ? rows : current, query, state, provider);
  const pages = Math.max(1, Math.ceil(shown.length / 24)), safePage = Math.min(page, pages - 1);
  const visible = shown.slice(safePage * 24, (safePage + 1) * 24);
  const change = setter => e => { setter(e.target.value); setPage(0); };
  return <main>
    <header><div className="brand"><span className="mark">N</span><span>nightshift <small>OPERATIONS</small></span></div><span className={'connection '+(error?'offline':'')}>{error?'Update interrupted':data?'Auto-refresh · 3s':'Connecting…'}</span></header>
    <section className="intro"><p className="eyebrow">YOUR LOCAL CONTROL ROOM</p><h1>See the work. Follow the evidence.</h1><p>Recorded run and gate states across your repository. Local evidence and workshop spec approval, on this machine.</p><code className="repo">{data?.root || 'Loading repository…'}</code></section>
    {error && <div className="notice" role="alert">{error}</div>}
    <WorkshopReviews />
    <section className="stats" aria-label="Current recorded run summary">{[
      ['In flight',current.filter(r=>active.has(r.state)).length,'active'],
      ['Needs attention',current.filter(r=>attention.has(r.state)).length,'attention'],
      ['Complete',current.filter(r=>r.state==='complete').length,'complete'],
      ['Checkouts',data?.checkouts.length || 0,'all']
    ].map(([label,value,filter])=><button className="stat" key={label} onClick={()=>{setState(filter);setHistory(false);setPage(0);}}><span>{label}</span><strong>{data?value:'—'}</strong><small>{label==='Checkouts'?'registered worktrees':'source observations'}</small></button>)}</section>
    <TicketActions rows={rows} />
    <ArtifactLibrary rows={rows} />
    <TicketUsage reports={data?.ticket_usage || []} />
    <section className="workspace" aria-label="Agents"><div className="section-title"><div><h2>Agents <span className="badge busy">{agents.filter(a=>a.state==='running').length} recorded running</span></h2><p>Factory and role lifecycle records. A running record is not a verified OS heartbeat; interrupted processes may leave stale records.</p></div><label>Agent state <select value={agentState} onChange={e=>{setAgentState(e.target.value);setAgentPage(0);}}>{['all','running','success','failed','interrupted'].map(s=><option key={s}>{s}</option>)}</select></label></div>
      {!filteredAgents.length && <div className="empty"><h3>No agent records in this view</h3><p>Factory runs and role invocations publish local lifecycle evidence here.</p></div>}
      <div className="cards">{filteredAgents.slice(safeAgentPage*12,(safeAgentPage+1)*12).map((agent,index)=><article className="run" key={(agent.links?.[0]?.href || agent.ticket)+index}><div className="run-head"><h3>{agent.ticket}</h3><span className={'badge '+(agent.state==='running'?'busy':agent.state==='success'?'done':'warn')}>{agent.ticket === 'nightshift-factory' && agent.state === 'success' ? 'Process exited' : agent.state}</span></div><div className="run-meta"><span>{agent.provider}</span><span>{agent.model}</span><span>PID {agent.pid}</span></div><p className="path" title={agent.checkout}>{agent.checkout}</p><p className="next">Started {agent.started_at}</p>{agent.ticket === 'nightshift-workshop' && <p>Execution: {agent.execution_status || 'unknown'} · Requirements verification: {agent.verification_status || 'unknown'}</p>}{agent.finished_at && <p>Finished {agent.finished_at}</p>}{agent.state === 'failed' && <p role="alert" className="reason">{(agent.ticket === 'nightshift-workshop' && rows.find(r => r.source === 'gate' && r.gate === 'workshop' && r.checkout === agent.checkout && r.reason)?.reason) || agent.reason}</p>}{agent.ticket === 'nightshift-factory' && agent.state === 'success' && <p>Factory process exited normally. Check the ticket outcome above for completion or blockers.</p>}<details><summary>Lifecycle source</summary><EvidenceLink link={agent.links?.[0]} /></details></article>)}</div>
      {agentPages>1 && <nav className="pagination" aria-label="Agent pages"><button disabled={!safeAgentPage} onClick={()=>setAgentPage(safeAgentPage-1)}>Previous</button><span>Page {safeAgentPage+1} of {agentPages} · 12 per page</span><button disabled={safeAgentPage+1>=agentPages} onClick={()=>setAgentPage(safeAgentPage+1)}>Next</button></nav>}
    </section>
    <section className="workspace"><div className="section-title"><div><h2>{history?'Historical evidence':'Run overview'}</h2><p>{history?'All source observations, including ownership and artifacts.':'Batch and gate observations remain independent. File timestamps sort the view; they never settle conflicting claims.'}</p></div><button className="secondary" onClick={()=>{setHistory(!history);setPage(0);setState('all');}}>{history?'← Run overview':'View history →'}</button></div>
    <div className="filters"><label className="search">Search<input value={query} onChange={change(setQuery)} placeholder="Ticket, stage, provider, checkout…" /></label><label>State<select value={state} onChange={change(setState)}>{['all','active','attention','pending','complete','failed','blocked'].map(s=><option key={s} value={s}>{s==='all'?'All states':s}</option>)}</select></label><label>Provider<select value={provider} onChange={change(setProvider)}><option value="all">All providers</option>{[...new Set(rows.map(r=>r.provider).filter(Boolean))].sort().map(p=><option key={p}>{p}</option>)}</select></label></div>
    <div className="result-note">{shown.length} {history?'observations':'run / gate observations'} · {data?'Snapshot '+new Date(data.generated_at).toLocaleTimeString():'Loading…'}<span>Recorded “in flight” does not confirm a live process.</span></div>
    {!visible.length && <div className="empty"><h3>{data?'Nothing in this view':'Reading durable state…'}</h3><p>{data?'Try another filter, or start a Nightshift run to produce evidence.':'The dashboard is collecting local records.'}</p></div>}
    <div className="cards">{visible.map((row,index)=><article className="run" key={[row.ticket,row.checkout,row.source,index].join(':')}><div className="run-head"><h3>{row.ticket}</h3><span className={'badge '+(attention.has(row.state)?'warn':active.has(row.state)?'busy':row.state==='complete'?'done':'')}>{row.state}</span></div><div className="run-meta"><span>{row.gate || 'unknown stage'}</span><span>{row.provider || 'unknown provider'}</span><span>{row.source}</span></div><p className="path" title={row.checkout}>{row.checkout}</p>{row.reason && <p className="reason">{row.reason}</p>}{row.next_action && <p className="next">Next: {row.next_action}</p>}<div>{row.pr_url_text && <EvidenceLink link={{href: row.pr_url_text, label: "Open pull request"}} />}</div><div className="run-footer"><span>Retries {row.attempted ?? 'unknown'} / {row.budget ?? 'unknown'}</span><span>{modified(row)?new Date(modified(row)*1000).toLocaleString():'No file timestamp'}</span></div><details><summary>Evidence & details</summary><p>File timestamps indicate source modification, not agent heartbeat.</p><p>Worktree: {row.worktree || 'unknown'}</p>{(row.links || []).filter(Boolean).map((link,i)=><div className="evidence" key={i}><EvidenceLink link={link} /></div>)}</details></article>)}</div>
    <nav className="pagination" aria-label="Results pages"><button disabled={!safePage} onClick={()=>setPage(safePage-1)}>Previous</button><span>Page {safePage+1} of {pages} · up to 24 per page</span><button disabled={safePage+1>=pages} onClick={()=>setPage(safePage+1)}>Next</button></nav></section>
    {!!(data?.warnings.length || data?.errors.length) && <details className="diagnostics"><summary>Collection notes · {data.warnings.length+data.errors.length}</summary>{data.warnings.map((w,i)=><p key={'w'+i}>{w}</p>)}{data.errors.slice(0,50).map((e,i)=><p key={i}>{e.ticket}: {e.message}</p>)}{data.errors.length>50 && <p>Showing the first 50 errors. Static output contains the complete bounded report.</p>}</details>}
    <footer>Local evidence. Version-bound spec approval. <span>Nightshift</span></footer>
  </main>;
}
createRoot(document.getElementById('root')).render(window.location.pathname === '/evidence' ? <EvidenceViewer /> : <App />);
