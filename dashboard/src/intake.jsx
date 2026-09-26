import React, {useEffect,useState} from 'react';

export function IntakePanel({onPrepared}) {
  const [identity,setIdentity]=useState(null),[token,setToken]=useState(''),[source,setSource]=useState('');
  const [scope,setScope]=useState(''),[requirements,setRequirements]=useState(''),[check,setCheck]=useState(''),[runner,setRunner]=useState('python3');
  const [rules,setRules]=useState(''),[architecture,setArchitecture]=useState(''),[operator,setOperator]=useState('');
  const [calls,setCalls]=useState(12),[seconds,setSeconds]=useState(180),[preview,setPreview]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  useEffect(()=>{fetch('/api/intake',{cache:'no-store'}).then(r=>r.json()).then(v=>{setIdentity(v.view?.runtime);setToken(v.token||'');if(v.error)setError(v.error);}).catch(e=>setError(e.message));},[]);
  const lines=value=>value.split('\n').map(x=>x.trim()).filter(Boolean);
  function choices(){return {scope:lines(scope),checks:check.trim()?[{id:'declared-check',argv:[runner,check.trim()]}]:[],requirements:lines(requirements).map((requirement,index)=>({id:'R'+(index+1),requirement,manual:false})),rules:rules.trim(),architecture:architecture.trim(),allowance:{calls:Number(calls),seconds:Number(seconds),wall_seconds:Number(seconds)}};}
  async function submit(action){
    setBusy(true);setError('');
    try{
      const answering=action==='preview'&&preview?.status==='needs_decision';
      const body=action==='preview'?{action:answering?'intake-answer':'intake-preview',source,choices:choices(),...(answering?{task:preview.task,binding:preview.binding}:{})}:{action:'intake-'+action,task:preview.task,binding:preview.binding,operator,request:crypto.randomUUID()};
      const response=await fetch('/api/operations',{method:'POST',headers:{'Content-Type':'application/json','X-Nightshift-Token':token},body:JSON.stringify(body)});
      const value=await response.json();if(!response.ok||value.status==='blocked')throw new Error(value.error||value.reason||'Intake unavailable');
      if(action==='preview')setPreview(value);
      else if(action==='apply'){setPreview({...preview,status:value.status});onPrepared(value.task);}
      else setPreview({...preview,status:'cancelled'});
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <section className="workspace intake-panel" aria-label="Guided intake"><h2>Start a request</h2>
    <p>Resolve a GitHub issue or project Markdown request, inspect its plan, then authorize operations separately.</p>
    {identity&&<><p>Serving candidate: <code>{identity.serving_revision}</code>. Installed runtime revision: {identity.installed_revision}. Delivery: {identity.endpoint}. Provider authentication: unverified; this preview makes no provider call.</p><p>Available tools: {Object.entries(identity.tools||{}).filter(([,present])=>present).map(([name])=>name).join(', ')||'none'}. Missing tools: {Object.entries(identity.tools||{}).filter(([,present])=>!present).map(([name])=>name).join(', ')||'none'}.</p></>}
    <label>Source reference<input disabled={busy} value={source} onChange={e=>{setSource(e.target.value);setPreview(null);}} placeholder="gh:owner/repository#123 or spec:request.md" /></label>
    <label>Source files in scope, one per line<textarea disabled={busy} value={scope} onChange={e=>setScope(e.target.value)} /></label>
    <label>Required behaviors, one per line<textarea disabled={busy} value={requirements} onChange={e=>setRequirements(e.target.value)} /></label>
    <label>Existing test script<input disabled={busy} value={check} onChange={e=>setCheck(e.target.value)} /></label>
    <label>Test runner<select disabled={busy} value={runner} onChange={e=>setRunner(e.target.value)}><option>python3</option><option>bash</option></select></label>
    <label>Project rules file<input disabled={busy} value={rules} onChange={e=>setRules(e.target.value)} /></label>
    <label>Architecture context file<input disabled={busy} value={architecture} onChange={e=>setArchitecture(e.target.value)} /></label>
    <label>Maximum provider calls<input disabled={busy} type="number" min="1" max="64" value={calls} onChange={e=>setCalls(e.target.value)} /></label>
    <label>Maximum execution and wall seconds<input disabled={busy} type="number" min="1" max="3600" value={seconds} onChange={e=>setSeconds(e.target.value)} /></label>
    <button disabled={busy||!token||!source.trim()} onClick={()=>submit('preview')}>{preview?.status==='needs_decision'?'Save choices and preview':'Preview request plan'}</button>
    {error&&<p role="alert">{error}</p>}
    {preview&&<><p>Status: {preview.status}. {preview.missing?.length?'Required choices: '+preview.missing.join(', '):''}</p>
      {preview.decision&&<p>{preview.decision.question} {preview.decision.reason}</p>}
      {preview.readiness&&<p>Execution readiness: {preview.readiness.admission.status}. {preview.readiness.admission.reason} {preview.readiness.admission.next_action}</p>}
      <details open><summary>Proposed request, plan and files</summary><pre>{JSON.stringify({source:preview.source,plan:preview.plan,files:preview.files,binding:preview.binding},null,2)}</pre></details>
      <label>Intake operator identity<input disabled={busy} value={operator} onChange={e=>setOperator(e.target.value)} /></label>
      <button disabled={busy||!operator.trim()||preview.status!=='preview'||JSON.stringify(choices())!==JSON.stringify(preview.options)} onClick={()=>submit('apply')}>Prepare inspected plan</button>
      <button disabled={busy||!operator.trim()||['cancelled','prepared'].includes(preview.status)} onClick={()=>submit('cancel')}>Cancel intake</button>
    </>}
  </section>;
}
