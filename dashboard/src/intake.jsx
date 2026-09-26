import React, {useEffect, useState} from 'react';

export function IntakePanel({onReady, onBusy, disabled = false}) {
  const [reference,setReference]=useState(''), [data,setData]=useState(null), [runtime,setRuntime]=useState(null);
  const [token,setToken]=useState(''), [busy,setBusy]=useState(false), [error,setError]=useState(''), [answer,setAnswer]=useState('');
  const [choices,setChoices]=useState({scope:'',rules:'',architecture:'',check:'',interpreter:'python3',requirement:''});
  useEffect(()=>{const abort=new AbortController();fetch('/api/intake',{cache:'no-store',signal:abort.signal}).then(async response=>{
    const value=await response.json();if(!response.ok)throw new Error(value.error||'Intake unavailable');setToken(value.token);setRuntime(value.view.runtime);
  }).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return()=>abort.abort();},[]);
  async function submit(body) {
    if (disabled) return;
    setBusy(true);onBusy(true);setError('');
    try {
      const response=await fetch('/api/intake',{method:'POST',headers:{'Content-Type':'application/json','X-Nightshift-Token':token},body:JSON.stringify(body)});
      const value=await response.json();if(!response.ok)throw new Error(value.error||'Intake blocked');setData(value);setRuntime(value.runtime);
      if(value.status==='materialized')await onReady(value.task);
    } catch(e){setError(e.message);}finally{setBusy(false);onBusy(false);}
  }
  const field=(name,label,multiline=false)=><label key={name}>{label}{multiline?<textarea value={choices[name]} onChange={e=>setChoices({...choices,[name]:e.target.value})}/>:<input value={choices[name]} onChange={e=>setChoices({...choices,[name]:e.target.value})}/>}</label>;
  return <section aria-label="Start new work">
    <h3>Start new work</h3>
    <p>Resolve a source, inspect a draft, then authorize engineering operations.</p>
    {runtime&&<details><summary>Serving and installed runtime</summary><p>Serving revision: {runtime.serving.revision||'unknown'}{runtime.serving.dirty?' (modified)':''}</p><p>Installed revision: {runtime.installed.revision||'unknown'}{runtime.installed.dirty?' (modified)':''}</p><p>Serving capabilities: {runtime.capabilities.join(', ')}</p></details>}
    <label>Source reference<input disabled={busy||disabled} placeholder="gh:owner/repository#123 or spec:request.md" value={reference} onChange={e=>setReference(e.target.value)}/></label>
    <button disabled={busy||disabled||!token||!reference.trim()} onClick={()=>submit({action:'resolve',reference:reference.trim()})}>Resolve source</button>
    {error&&<p role="alert">{error}</p>}
    {data&&<><p>Intake status: {data.status}. Task: {data.task}</p>
      <p>Delivery: local checkout {data.endpoint.branch||'(detached)'}. {data.endpoint.project}</p>
      <p>Source: {data.source?.record.title}. Readiness: manifest {data.readiness.manifest}; routing {data.readiness.routing}; authentication unverified. Readiness does not call a model.</p>
      <details><summary>Source snapshot and readiness</summary><pre>{JSON.stringify({source:data.source,readiness:data.readiness},null,2)}</pre></details>
      {!['cancelled','materialized'].includes(data.status)&&<fieldset disabled={busy||disabled}>
        <legend>Declare the work boundary</legend>
        {field('scope','Files to change (one path per line)',true)}
        {field('rules','Project rules file')}{field('architecture','Architecture guidance file')}
        {field('check','Verification script')}
        <label>Verification interpreter<select value={choices.interpreter} onChange={e=>setChoices({...choices,interpreter:e.target.value})}><option>python3</option><option>bash</option></select></label>
        {field('requirement','Required acceptance behavior',true)}
        <button onClick={()=>submit({action:'draft',task:data.task,choices:{...choices,scope:choices.scope.split('\n').map(s=>s.trim()).filter(Boolean)}})}>Prepare inspectable draft</button>
        {data.decisions.pending.map(question=><div key={question.sha256}><p>{question.question}</p><label>Product choice answer<textarea value={answer} onChange={e=>setAnswer(e.target.value)}/></label><button disabled={!answer.trim()} onClick={()=>submit({action:'answer',task:data.task,sha256:question.sha256,answer})}>Save choice without starting work</button></div>)}
        {data.draft&&<><details open><summary>Proposed plan and files</summary><pre>{JSON.stringify(data.draft.artifacts,null,2)}</pre></details><p>Bounded draft: 16 calls, 600 execution seconds, 900 wall seconds. Existing routing remains configured; publication requires separate authority.</p><button onClick={()=>submit({action:'materialize',task:data.task,binding:data.draft.binding})}>Create draft files</button></>}
        <button onClick={()=>submit({action:'cancel',task:data.task})}>Cancel intake and retain evidence</button>
      </fieldset>}
    </>}
  </section>;
}
