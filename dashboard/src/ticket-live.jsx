import React, {useEffect, useState} from 'react';

const duration = seconds => typeof seconds !== 'number' ? 'Unknown' : seconds < 60 ? `${Math.floor(seconds)}s` : `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
const time = value => value ? new Date(typeof value === 'number' ? value * 1000 : value).toLocaleTimeString() : 'No activity recorded';

export function LiveProgress({ticket}) {
  const live = ticket.progress;
  if (!live) return <section className="live-progress"><h4>You are here</h4><p>Waiting for a live progress snapshot. Recorded gates remain below.</p></section>;
  return <section className="live-progress" aria-label="Live ticket progress">
    <div className="run-head"><h4>You are here</h4><span className={'badge '+(ticket.running?'busy':'')}>{live.phase || 'Status unavailable'}</span></div>
    <p className="live-activity">{live.activity}</p>
    {(live.workers || []).map((worker, index) => <p className="run-meta" key={index}><span>{worker.role}</span><span>{worker.provider} · {worker.model}</span><span>{duration(worker.elapsed_seconds)} elapsed</span></p>)}
    <dl className="live-facts"><div><dt>Action needed</dt><dd>{live.action_required || 'Check the latest receipt'}</dd></div><div><dt>Next</dt><dd>{live.next || 'Await a recorded result'}</dd></div><div><dt>Last activity</dt><dd>{time(live.last_activity_at)}{typeof live.last_activity_age_seconds === 'number' && ` · ${duration(live.last_activity_age_seconds)} ago`}</dd></div></dl>
    {live.latest_event && <details className="latest-event" open><summary>Latest recorded update</summary><p>{live.latest_event}</p></details>}
    <small>Activity describes live processes. The timeline below records gate outcomes; an active repair does not erase a failed gate.</small>
  </section>;
}

export function TicketChat({ticket, token}) {
  const [open,setOpen] = useState(false), [state,setState] = useState({messages:[],running:false});
  const [message,setMessage] = useState(''), [provider,setProvider] = useState('auto'), [busy,setBusy] = useState(false), [error,setError] = useState('');
  useEffect(() => {
    if (!open) return;
    let disposed=false, timer; const controller=new AbortController();
    async function refresh() {
      try {
        const response=await fetch('/api/tickets/chat?task='+encodeURIComponent(ticket.task),{cache:'no-store',signal:controller.signal});
        const value=await response.json();
        if (!response.ok) throw new Error(value.error || 'Chat unavailable; refresh the dashboard server.');
        if (!disposed) setState(value);
      } catch(e) {if (!disposed && e.name!=='AbortError') setError(e.message);}
      if (!disposed) timer=setTimeout(refresh,3000);
    }
    refresh();return()=>{disposed=true;clearTimeout(timer);controller.abort();};
  },[open,ticket.task]);
  async function send(event) {
    event.preventDefault();if (!message.trim() || busy || state.running) return;
    setBusy(true);setError('');
    try {
      const response=await fetch('/api/tickets/chat',{method:'POST',headers:{'Content-Type':'application/json','X-Nightshift-Token':token},body:JSON.stringify({task:ticket.task,sha256:ticket.sha256,provider,message:message.trim()})});
      const value=await response.json();
      if (!response.ok) throw new Error(value.error || 'Chat could not start');
      setState(current=>({...current,running:true,phase:'starting'}));setMessage('');
    } catch(e) {setError(e.message);} finally {setBusy(false);}
  }
  return <details className="ticket-chat" onToggle={event=>setOpen(event.currentTarget.open)}><summary>Ask about this ticket</summary>
    <p>Read-only answers grounded in this ticket’s public evidence. Chat cannot change files, steer workers, or start repairs. No automatic provider fallback.</p>
    <p>Claude and local chat are available. If your configured default routes to Codex, select Claude or Local explicitly; Codex chat is unavailable until its tool-free execution is verified.</p>
    <div className="chat-messages" aria-label="Ticket conversation">{(state.messages || []).map((item,index)=><article key={index} className={'chat-message '+item.role}><strong>{item.role==='user'?'You':`${item.provider || 'Assistant'}${item.model ? ' · '+item.model : ''}`}</strong><p>{item.content}</p>{item.citations?.length>0 && <ul>{item.citations.map((c,i)=><li key={i}>{typeof c==='string'?c:`[${c.source_id}] ${c.label || c.path || c.source_id}`}{c.line ? ':'+c.line : ''}</li>)}</ul>}</article>)}</div>
    {(error || state.error) && <p role="alert" className="notice">{error || state.error}</p>}
    <p role="status">{state.running ? `Answering · ${state.provider || provider} ${state.model || ''} · ${state.phase || 'running'}` : 'Ready for a question'}</p>
    <form onSubmit={send}><label>Chat provider <select value={provider} disabled={busy || state.running} onChange={event=>setProvider(event.target.value)}><option value="auto">Configured default</option><option value="claude">Claude</option>{ticket.settings.policy !== 'claude-only' && <><option value="codex" disabled>Codex — unavailable in read-only chat</option><option value="local">Local model</option></>}</select></label><label className="chat-question">Your question<textarea maxLength={2000} rows={3} value={message} disabled={busy || state.running} onChange={event=>setMessage(event.target.value)} placeholder="What is happening now, and does this ticket need my attention?" /></label><button disabled={busy || state.running || !message.trim()} type="submit">Ask</button></form>
  </details>;
}
