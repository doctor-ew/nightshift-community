import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { active, attention, currentRows, filterRows, modified } from './model.mjs';
import './app.css';

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
    <section className="intro"><p className="eyebrow">YOUR LOCAL CONTROL ROOM</p><h1>See the work. Follow the evidence.</h1><p>Recorded run and gate states across your repository. Read-only, on this machine.</p><code className="repo">{data?.root || 'Loading repository…'}</code></section>
    {error && <div className="notice" role="alert">{error}</div>}
    <section className="stats" aria-label="Current recorded run summary">{[
      ['In flight',current.filter(r=>active.has(r.state)).length,'active'],
      ['Needs attention',current.filter(r=>attention.has(r.state)).length,'attention'],
      ['Complete',current.filter(r=>r.state==='complete').length,'complete'],
      ['Checkouts',data?.checkouts.length || 0,'all']
    ].map(([label,value,filter])=><button className="stat" key={label} onClick={()=>{setState(filter);setHistory(false);setPage(0);}}><span>{label}</span><strong>{data?value:'—'}</strong><small>{label==='Checkouts'?'registered worktrees':'source observations'}</small></button>)}</section>
    <section className="workspace" aria-label="Agents"><div className="section-title"><div><h2>Agents <span className="badge busy">{agents.filter(a=>a.state==='running').length} recorded running</span></h2><p>Dispatcher lifecycle records. A running record is not a verified OS heartbeat; interrupted processes may leave stale records.</p></div><label>Agent state <select value={agentState} onChange={e=>{setAgentState(e.target.value);setAgentPage(0);}}>{['all','running','success','failed','interrupted'].map(s=><option key={s}>{s}</option>)}</select></label></div>
      {!filteredAgents.length && <div className="empty"><h3>No agent records in this view</h3><p>New shared-dispatcher invocations publish local lifecycle evidence here.</p></div>}
      <div className="cards">{filteredAgents.slice(safeAgentPage*12,(safeAgentPage+1)*12).map((agent,index)=><article className="run" key={(agent.links?.[0]?.href || agent.ticket)+index}><div className="run-head"><h3>{agent.ticket}</h3><span className={'badge '+(agent.state==='running'?'busy':agent.state==='success'?'done':'warn')}>{agent.state}</span></div><div className="run-meta"><span>{agent.provider}</span><span>{agent.model}</span><span>PID {agent.pid}</span></div><p className="path" title={agent.checkout}>{agent.checkout}</p><p className="next">Started {agent.started_at}</p>{agent.finished_at && <p>Finished {agent.finished_at}</p>}<details><summary>Lifecycle source</summary><code className="repo">{agent.links?.[0]?.href}</code></details></article>)}</div>
      {agentPages>1 && <nav className="pagination" aria-label="Agent pages"><button disabled={!safeAgentPage} onClick={()=>setAgentPage(safeAgentPage-1)}>Previous</button><span>Page {safeAgentPage+1} of {agentPages} · 12 per page</span><button disabled={safeAgentPage+1>=agentPages} onClick={()=>setAgentPage(safeAgentPage+1)}>Next</button></nav>}
    </section>
    <section className="workspace"><div className="section-title"><div><h2>{history?'Historical evidence':'Run overview'}</h2><p>{history?'All source observations, including ownership and artifacts.':'Batch and gate observations remain independent. File timestamps sort the view; they never settle conflicting claims.'}</p></div><button className="secondary" onClick={()=>{setHistory(!history);setPage(0);setState('all');}}>{history?'← Run overview':'View history →'}</button></div>
    <div className="filters"><label className="search">Search<input value={query} onChange={change(setQuery)} placeholder="Ticket, stage, provider, checkout…" /></label><label>State<select value={state} onChange={change(setState)}>{['all','active','attention','pending','complete','failed','blocked'].map(s=><option key={s} value={s}>{s==='all'?'All states':s}</option>)}</select></label><label>Provider<select value={provider} onChange={change(setProvider)}><option value="all">All providers</option>{[...new Set(rows.map(r=>r.provider).filter(Boolean))].sort().map(p=><option key={p}>{p}</option>)}</select></label></div>
    <div className="result-note">{shown.length} {history?'observations':'run / gate observations'} · {data?'Snapshot '+new Date(data.generated_at).toLocaleTimeString():'Loading…'}<span>Recorded “in flight” does not confirm a live process.</span></div>
    {!visible.length && <div className="empty"><h3>{data?'Nothing in this view':'Reading durable state…'}</h3><p>{data?'Try another filter, or start a Nightshift run to produce evidence.':'The dashboard is collecting local records.'}</p></div>}
    <div className="cards">{visible.map((row,index)=><article className="run" key={[row.ticket,row.checkout,row.source,index].join(':')}><div className="run-head"><h3>{row.ticket}</h3><span className={'badge '+(attention.has(row.state)?'warn':active.has(row.state)?'busy':row.state==='complete'?'done':'')}>{row.state}</span></div><div className="run-meta"><span>{row.gate || 'unknown stage'}</span><span>{row.provider || 'unknown provider'}</span><span>{row.source}</span></div><p className="path" title={row.checkout}>{row.checkout}</p>{row.reason && <p className="reason">{row.reason}</p>}{row.next_action && <p className="next">Next: {row.next_action}</p>}<div className="run-footer"><span>Retries {row.attempted ?? 'unknown'} / {row.budget ?? 'unknown'}</span><span>{modified(row)?new Date(modified(row)*1000).toLocaleString():'No file timestamp'}</span></div><details><summary>Evidence & details</summary><p>File timestamps indicate source modification, not agent heartbeat.</p><p>Worktree: {row.worktree || 'unknown'}</p>{(row.links || []).filter(Boolean).map((link,i)=><div className="evidence" key={i}><strong>{link.label}</strong><code>{link.href}</code></div>)}</details></article>)}</div>
    <nav className="pagination" aria-label="Results pages"><button disabled={!safePage} onClick={()=>setPage(safePage-1)}>Previous</button><span>Page {safePage+1} of {pages} · up to 24 per page</span><button disabled={safePage+1>=pages} onClick={()=>setPage(safePage+1)}>Next</button></nav></section>
    {!!(data?.warnings.length || data?.errors.length) && <details className="diagnostics"><summary>Collection notes · {data.warnings.length+data.errors.length}</summary>{data.warnings.map((w,i)=><p key={'w'+i}>{w}</p>)}{data.errors.slice(0,50).map((e,i)=><p key={i}>{e.ticket}: {e.message}</p>)}{data.errors.length>50 && <p>Showing the first 50 errors. Static output contains the complete bounded report.</p>}</details>}
    <footer>Local evidence. No run controls. <span>Nightshift</span></footer>
  </main>;
}
createRoot(document.getElementById('root')).render(<App />);
