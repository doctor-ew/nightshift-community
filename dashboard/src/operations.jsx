import React, {useState} from 'react';

export function OperationsPanel() {
  const [task, setTask] = useState(''), [data, setData] = useState(null), [token, setToken] = useState('');
  const [operator, setOperator] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [authorProvider, setAuthorProvider] = useState(''), [authorModel, setAuthorModel] = useState('');
  const [selected, setSelected] = useState(null), [author, setAuthor] = useState(''), [accepted, setAccepted] = useState(false);
  async function inspect(clearError = true) {
    if (clearError) setError('');
    try {
      const response = await fetch('/api/operations?task=' + encodeURIComponent(task), {cache:'no-store'});
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || 'Operation assessment unavailable');
      setData(value.view); setToken(value.token);
    } catch(e) {setError(e.message);}
  }
  async function post(body) {
    const response = await fetch('/api/operations', {method:'POST',headers:{'Content-Type':'application/json','X-Nightshift-Token':token},body:JSON.stringify({task,...body})});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || 'Operation failed');
    return value;
  }
  async function authorizeRun() {
    setBusy(true); setError('');
    try {
      const operations=selected.operations;
      const first=data.operations.find(row=>row.operation===operations[0]);
      const attestation=first.operation==='adopt' ? {binding:first.binding,identity:author,provider:authorProvider,model:authorModel||'unknown'} : first.operation==='accept' ? {binding:first.binding,accepted} : first.operation==='publish' ? {binding:first.binding,publication:first.dependencies.publication} : undefined;
      const grant=await post({action:'authorize',operations,binding:first.binding,operator,request:crypto.randomUUID(),...(attestation ? {attestation} : {})});
      const result=await post({action:'chain',grant:grant.id});
      const failed=result.results.find(row=>!['passed','reused'].includes(row.status));
      if (failed) setError(failed.reason || failed.next_action || failed.status);
      setSelected(null); await inspect(false);
    } catch(e) {setError(e.message);} finally {setBusy(false);}
  }
  async function importDraft() {
    setBusy(true); setError('');
    try {await post({action:'migrate',operator,request:crypto.randomUUID()});await inspect(false);}
    catch(e) {setError(e.message);} finally {setBusy(false);}
  }
  async function resume(id) {
    setBusy(true);setError('');
    try {const result=await post({action:'chain',grant:id});const failed=result.results.find(row=>!['passed','reused'].includes(row.status));if(failed)setError(failed.reason||failed.next_action||failed.status);await inspect(false);}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <section className="workspace operations-panel" aria-label="Engineering operations">
    <h2>Engineering operations</h2>
    <p>Inspect retained artifacts, then authorize one operation or a bounded recipe. Existing ticket history remains below.</p>
    <label>Task key<input disabled={busy} value={task} onChange={e=>{setTask(e.target.value);setData(null);setSelected(null);}} /></label>
    <button disabled={busy||!task.trim()} onClick={async()=>{setBusy(true);try{await inspect();}finally{setBusy(false);}}}>Assess operations</button>
    {error && <p role="alert">{error}</p>}
    {data && <><p>Status: {data.status}</p>
      <label>Operator identity<input value={operator} onChange={e=>setOperator(e.target.value)} /></label>
      <button disabled={busy||!operator.trim()} onClick={importDraft}>Import retained draft without a worker</button>
      <div className="artifact-library">{data.operations.map(row=><div className="artifact-row" key={row.operation}>
        <strong>{row.operation}</strong><span>{row.status}. Next: {row.next_action}</span>
        <button disabled={busy||row.status==='blocked'} onClick={()=>{setSelected({operations:[row.operation]});setAccepted(false);}}>Select {row.operation}</button>
        <details><summary>Findings, evidence and allowance</summary><pre>{JSON.stringify({blockers:row.blockers,findings:row.findings,evidence:row.result?.evidence,allowance:row.allowance},null,2)}</pre></details>
      </div>)}</div>
      {Object.entries(data.recipes).map(([name,operations])=><button key={name} disabled={busy} onClick={()=>{setSelected({operations});setAccepted(false);}}>Select {name} recipe</button>)}
      {selected && <div><p>Selected operations: {selected.operations.join(' → ')}</p>
        <p>Aggregate ceiling: {data.operations.find(r=>r.operation===selected.operations[0])?.aggregate?.calls} provider calls; {data.operations.find(r=>r.operation===selected.operations[0])?.aggregate?.seconds} provider execution seconds. Stops at the first failure. Manual acceptance and publication remain separate.</p>
        {selected.operations[0]==='adopt' && <><label>External author identity<input value={author} onChange={e=>setAuthor(e.target.value)} /></label><label>Actual author provider<select value={authorProvider} onChange={e=>setAuthorProvider(e.target.value)}><option value="">Select actual author</option>{['human','codex','claude','local'].map(p=><option key={p}>{p}</option>)}</select></label><label>Actual author model (if known)<input value={authorModel} onChange={e=>setAuthorModel(e.target.value)} /></label></>}
        {selected.operations[0]==='accept' && <label><input type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)} />I completed the declared manual acceptance cases for this exact evidence.</label>}
        {selected.operations[0]==='publish' && <p>Publish target: {JSON.stringify({target:data.operations.find(r=>r.operation==='publish')?.dependencies?.publication,remote:data.operations.find(r=>r.operation==='publish')?.dependencies?.publication_target})}</p>}
        <button disabled={busy||!operator.trim()||(selected.operations[0]==='adopt'&&(!author.trim()||!authorProvider))||(selected.operations[0]==='accept'&&!accepted)} onClick={authorizeRun}>Authorize and run selected operations</button>
      </div>}
      <details><summary>Retained authorizations and recovery</summary>{Object.values(data.authorizations).map(g=><div key={g.id}><p>{g.id}: {g.operations.join(' → ')}</p><button disabled={busy} onClick={()=>resume(g.id)}>Resume {g.id}</button></div>)}<pre>{JSON.stringify({usage:data.usage,attempts:data.attempts,calls:data.calls},null,2)}</pre></details>
    </>}
  </section>;
}
