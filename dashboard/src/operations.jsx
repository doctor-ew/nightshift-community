import React, {useState} from 'react';
import {IntakePanel} from './intake.jsx';

export function OperationsPanel() {
  const [packages, setPackages] = useState(null);
  const [task, setTask] = useState(''), [data, setData] = useState(null), [token, setToken] = useState('');
  const [operator, setOperator] = useState(''), [operationBusy, setBusy] = useState(false), [error, setError] = useState('');
  const [intakeBusy, setIntakeBusy] = useState(false);
  const busy=operationBusy||intakeBusy;
  const [authorProvider, setAuthorProvider] = useState(''), [authorModel, setAuthorModel] = useState('');
  const [selected, setSelected] = useState(null), [author, setAuthor] = useState(''), [accepted, setAccepted] = useState(false);
  const [caseNotes,setCaseNotes]=useState({});
  const [answers,setAnswers]=useState({});
  const [liveGrant,setLiveGrant]=useState(null),[cancelPending,setCancelPending]=useState(false),[notice,setNotice]=useState('');
  async function cancelGrant(grant,binding){
    setCancelPending(true);
    try{await post({action:grant.package?'packages-cancel':'cancel',grant:grant.id,binding,operator:grant.operator,request:crypto.randomUUID()});setNotice('Cancellation requested. Owned local execution must stop before reconciliation; remote effects and unknown usage remain explicit.');}
    catch(e){setError(e.message);}finally{setCancelPending(false);}
  }
  async function reconcile(row,resolution){
    setBusy(true);setError('');
    try{await post({action:'reconcile',request:row.request,binding:row.binding,operator,resolution});await inspect(false);}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function answerQuestion(row,question){
    setBusy(true);setError('');
    try{await post({action:'answer',operation:row.operation,binding:row.binding,question:question.sha256,answer:answers[question.sha256]||''});await inspect(false);}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function inspect(clearError = true) {
    if (clearError) setError('');
    try {
      const response = await fetch('/api/operations?task=' + encodeURIComponent(task), {cache:'no-store'});
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || 'Operation assessment unavailable');
      setData(value.view); setToken(value.token);setAccepted(false);setCaseNotes({});setSelected(null);
    } catch(e) {setError(e.message);}
  }
  async function post(body) {
    const response = await fetch('/api/operations', {method:'POST',headers:{'Content-Type':'application/json','X-Nightshift-Token':token},body:JSON.stringify({task,...body})});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || 'Operation failed');
    return value;
  }
  async function inspectPackages() {
    setBusy(true);setError('');
    try {setPackages(await post({action:'packages-view'}));}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function runPackages(prepare = false, resumeGrant = null) {
    setBusy(true);setError('');
    try {
      let result;
      if (prepare) {
        const first=data.operations.find(row=>row.operation==='groom-spec');
        const grant=await post({action:'authorize',operations:data.recipes.groom,binding:first.binding,operator,request:crypto.randomUUID()});
        setLiveGrant(grant);
        result=await post({action:'packages-prepare',grant:grant.id});
      } else {
        const grant=resumeGrant ? packages.state.authorizations[resumeGrant] : await post({action:'packages-authorize',binding:packages.assessment.binding,operator,request:crypto.randomUUID()});
        setLiveGrant({...grant,package:true});
        result=await post({action:'packages-run',grant:grant.id});
      }
      if(result.status==='blocked')setError(result.reason||result.result?.reason||'Inspect package evidence.');
      setPackages(await post({action:'packages-view'}));await inspect(false);
    } catch(e){setError(e.message);}finally{setLiveGrant(null);setBusy(false);}
  }
  async function authorizeRun() {
    setBusy(true); setError('');
    try {
      const operations=selected.operations;
      const first=data.operations.find(row=>row.operation===operations[0]);
      const attestation=first.operation==='adopt' ? {binding:first.binding,identity:author,provider:authorProvider,model:authorModel||'unknown'} : first.operation==='accept' ? (first.manual_cases?.length ? {binding:first.binding,cases:first.manual_cases.map(c=>({id:c.id,case_sha256:c.case_sha256,passed:caseNotes[c.id]?.passed===true,observation:caseNotes[c.id]?.observation||'',evidence:caseNotes[c.id]?.evidence||''}))} : {binding:first.binding,accepted}) : first.operation==='publish' ? {binding:first.binding,publication:first.dependencies.publication} : selected.boundedRepair ? {bounded_repair:true} : undefined;
      const grant=await post({action:'authorize',operations,binding:first.binding,operator,request:crypto.randomUUID(),...(attestation ? {attestation} : {})});
      setLiveGrant(grant);
      const result=await post({action:selected.boundedRepair ? 'supervise' : 'chain',grant:grant.id});
      const failed=result.results?.find(row=>!['passed','reused'].includes(row.status));
      if (result.status==='blocked') setError(result.reason || result.supervisor?.reason || 'Inspect retained repair evidence.');
      if (failed) setError(failed.reason || failed.next_action || failed.status);
      setSelected(null); await inspect(false);
    } catch(e) {setError(e.message);} finally {setLiveGrant(null);setBusy(false);}
  }
  async function importDraft() {
    setBusy(true); setError('');
    try {await post({action:'migrate',operator,request:crypto.randomUUID()});await inspect(false);}
    catch(e) {setError(e.message);} finally {setBusy(false);}
  }
  async function resume(id) {
    setBusy(true);setError('');
    try {const result=await post({action:data.authorizations[id].attestation?.bounded_repair ? 'supervise' : 'chain',grant:id});if(result.status==='blocked')setError(result.reason||result.supervisor?.reason||'Inspect retained repair evidence.');const failed=result.results?.find(row=>!['passed','reused'].includes(row.status));if(failed)setError(failed.reason||failed.next_action||failed.status);await inspect(false);}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <><IntakePanel blocked={operationBusy} onBusy={setIntakeBusy} onPrepared={value=>{setTask(value);setData(null);setSelected(null);setPackages(null);}} /><section className="workspace operations-panel" aria-label="Engineering operations">
    <h2>Engineering operations</h2>
    <p>Inspect retained artifacts, then authorize one operation or a bounded recipe. Existing ticket history remains below.</p>
    <label>Task key<input disabled={busy} value={task} onChange={e=>{setTask(e.target.value);setData(null);setSelected(null);setPackages(null);}} /></label>
    <button disabled={busy||!task.trim()} onClick={async()=>{setBusy(true);try{await inspect();}finally{setBusy(false);}}}>Assess operations</button>
    {error && <p role="alert">{error}</p>}
    {notice&&<p role="status">{notice}</p>}
    {liveGrant&&<button disabled={cancelPending} onClick={()=>cancelGrant(liveGrant,liveGrant.cancellation_binding)}>Request cancellation of active operations</button>}
    {data && <><p>Status: {data.status}</p>
      <label>Operator identity<input value={operator} onChange={e=>setOperator(e.target.value)} /></label>
      <button disabled={busy} onClick={inspectPackages}>Inspect work packages</button>
      {packages && <section aria-label="Work-package composition"><h3>Work packages</h3>
        <p>Status: {packages.assessment.status}. {packages.assessment.reason}</p>
        <p>Parent ceiling: {packages.assessment.graph?.aggregate.calls} provider calls; {packages.assessment.graph?.aggregate.seconds} execution seconds, including preparation and all children.</p>
        <button disabled={busy||!operator.trim()} onClick={()=>runPackages(true)}>Authorize decomposition preparation and challenge</button>
        <button disabled={busy||!operator.trim()||packages.assessment.status!=='ready'} onClick={()=>runPackages()}>Authorize bounded package composition</button>
        {Object.values(packages.state.authorizations).map(grant=><div key={grant.id}><button disabled={busy||!!packages.cancellations?.[grant.id]?.intent} onClick={()=>runPackages(false,grant.id)}>Resume package grant {grant.id}</button><button disabled={cancelPending||!!packages.cancellations?.[grant.id]?.intent} onClick={()=>cancelGrant({...grant,package:true},packages.cancellations[grant.id].binding)}>Cancel package grant {grant.id}</button></div>)}
        <details><summary>Package dependencies, allocations and evidence</summary><pre>{JSON.stringify(packages,null,2)}</pre></details>
      </section>}
      <button disabled={busy||!operator.trim()} onClick={importDraft}>Import retained draft without a worker</button>
      <div className="artifact-library">{data.operations.map(row=><div className="artifact-row" key={row.operation}>
        <strong>{row.operation}</strong><span>{row.status}. Next: {row.next_action}</span>
        <button disabled={busy||row.status==='blocked'} onClick={()=>{setSelected({operations:[row.operation]});setAccepted(false);setCaseNotes({});}}>Select {row.operation}</button>
        {(row.questions||[]).map(q=><div key={q.sha256}><p>{q.current?'Current clarification':'Retained clarification from changed evidence'}: {q.question.question}</p><p>{q.question.reason}</p>{q.question.options.map(o=><p key={o.id}>{o.label}: {o.description}</p>)}{q.question.response?<p>Saved answer: {q.question.response.selected?.label} {q.question.response.answer}</p>:q.current&&<><label>Answer for {row.operation}<textarea disabled={busy} maxLength={4000} value={answers[q.sha256]||''} onChange={e=>setAnswers({...answers,[q.sha256]:e.target.value})} /></label><button disabled={busy||!answers[q.sha256]?.trim()} onClick={()=>answerQuestion(row,q)}>Save answer without running</button><p>This saves context for the next explicitly authorized operation. It grants no allowance.</p></>}</div>)}
        {row.blockers?.length>0&&<p>Next action: {row.blockers.includes('operator_decision_required')?'Answer the current clarification, then reassess and authorize continuation.':row.blockers.includes('repair_limit_exhausted')?'Automatic repair is exhausted. Preserve the receipt; implement externally, then select adopt with the actual author before fresh verification and review.':row.blockers.some(b=>b.startsWith('missing_current_results'))?'Run or repair the required preceding operations, then reassess this evidence.':'Inspect the retained failure and changed inputs; reassess before authorizing another operation.'}</p>}
        {row.operation==='verify'&&row.result?.observations?.length>0&&<details><summary>Typed verification observations</summary><pre>{JSON.stringify(row.result.observations.map(({id,adapter,status,complete,counts,reason,raw_evidence})=>({id,adapter,status,complete,counts,reason,raw_evidence})),null,2)}</pre></details>}
        <details><summary>Findings, evidence and allowance</summary><pre>{JSON.stringify({blockers:row.blockers,findings:row.findings,evidence:row.result?.evidence,allowance:row.allowance},null,2)}</pre></details>
      </div>)}</div>
      {Object.entries(data.recipes).map(([name,operations])=><button key={name} disabled={busy} onClick={()=>{setSelected({operations});setAccepted(false);setCaseNotes({});}}>Select {name} recipe</button>)}
      {selected && <div><p>Selected operations: {selected.operations.join(' → ')}</p>
        <p>Aggregate ceiling: {data.operations.find(r=>r.operation===selected.operations[0])?.aggregate?.calls} provider calls; {data.operations.find(r=>r.operation===selected.operations[0])?.aggregate?.seconds} provider execution seconds. Eligible automatic repairs use this same ceiling when explicitly selected. Manual acceptance and publication remain separate.</p>
        {['factory','groom'].some(name=>JSON.stringify(data.recipes[name])===JSON.stringify(selected.operations)) && <label><input type="checkbox" checked={!!selected.boundedRepair} onChange={e=>setSelected({...selected,boundedRepair:e.target.checked})} />Repair eligible failures within this allowance</label>}
        {selected.operations[0]==='adopt' && <><label>External author identity<input value={author} onChange={e=>setAuthor(e.target.value)} /></label><label>Actual author provider<select value={authorProvider} onChange={e=>setAuthorProvider(e.target.value)}><option value="">Select actual author</option>{['human','codex','claude','local'].map(p=><option key={p}>{p}</option>)}</select></label><label>Actual author model (if known)<input value={authorModel} onChange={e=>setAuthorModel(e.target.value)} /></label></>}
        {selected.operations[0]==='accept' && <><p>These observations attest only to the currently assessed evidence. Changed evidence requires reassessment.</p>{(data.operations.find(r=>r.operation==='accept')?.manual_cases||[]).map(c=><fieldset key={c.case_sha256} disabled={busy}><legend>{c.id}: {c.requirement}</legend><label>Observed result for {c.id}<textarea maxLength={2048} value={caseNotes[c.id]?.observation||''} onChange={e=>setCaseNotes({...caseNotes,[c.id]:{...caseNotes[c.id],observation:e.target.value}})} /></label><label>Evidence note for {c.id}<textarea maxLength={2048} value={caseNotes[c.id]?.evidence||''} onChange={e=>setCaseNotes({...caseNotes,[c.id]:{...caseNotes[c.id],evidence:e.target.value}})} /></label><label><input type="checkbox" checked={caseNotes[c.id]?.passed||false} onChange={e=>setCaseNotes({...caseNotes,[c.id]:{...caseNotes[c.id],passed:e.target.checked}})} />Manual case {c.id} passed</label></fieldset>)}<label><input type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)} />I accept this exact reviewed evidence and the recorded case observations.</label></>}
        {selected.operations[0]==='publish' && <p>Publish target: {JSON.stringify({target:data.operations.find(r=>r.operation==='publish')?.dependencies?.publication,remote:data.operations.find(r=>r.operation==='publish')?.dependencies?.publication_target})}</p>}
        <button disabled={busy||!operator.trim()||(selected.operations[0]==='adopt'&&(!author.trim()||!authorProvider))||(selected.operations[0]==='accept'&&(!accepted||(data.operations.find(r=>r.operation==='accept')?.manual_cases||[]).some(c=>!caseNotes[c.id]?.passed||!caseNotes[c.id]?.observation?.trim()||!caseNotes[c.id]?.evidence?.trim())))} onClick={authorizeRun}>Authorize and run selected operations</button>
      </div>}
      <details><summary>Retained authorizations and recovery</summary>{Object.values(data.authorizations).map(g=><div key={g.id}><p>{g.id}: {g.operations.join(' → ')}</p><button disabled={busy||!!data.cancellations?.[g.id]?.intent} onClick={()=>resume(g.id)}>Resume {g.id}</button><button disabled={cancelPending||!!data.cancellations?.[g.id]?.intent} onClick={()=>cancelGrant(g,data.cancellations[g.id].binding)}>Cancel remaining operations {g.id}</button></div>)}{(data.reconciliation||[]).map(row=><div key={row.request}><p>{row.request}: {row.status}. Remote execution: {row.remote_execution}. Reconciliation never dispatches a provider.</p>{row.actions.includes('finalize')&&<button disabled={busy||!operator.trim()} onClick={()=>reconcile(row,'finalize')}>Finalize retained completion {row.request}</button>}{row.actions.includes('preserve')&&<button disabled={busy||!operator.trim()} onClick={()=>reconcile(row,'preserve')}>Preserve cancelled unknown execution {row.request}</button>}</div>)}<pre>{JSON.stringify({cancellations:data.cancellations,supervisors:data.supervisors,usage:data.usage,attempts:data.attempts,calls:data.calls},null,2)}</pre></details>
    </>}
  </section></>;
}
