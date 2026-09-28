import React,{useState} from 'react';

export function DeliveryPanel({operator,post,busy,setBusy,onError,refreshOperations,operationsView}){
  const [action,setAction]=useState('deliver'),[assessment,setAssessment]=useState(null),[view,setView]=useState(null),[result,setResult]=useState(null),[live,setLive]=useState(null),[cancelling,setCancelling]=useState(false),[repairGrant,setRepairGrant]=useState('');
  const repairChoices=Object.values(operationsView.authorizations).filter(grant=>grant.attestation?.bounded_repair&&grant.operator===operator&&JSON.stringify(grant.operations)===JSON.stringify(operationsView.recipes.factory));
  const selectedRepair=repairChoices.some(grant=>grant.id===repairGrant&&grant.deadline*1000>Date.now()&&!operationsView.cancellations[grant.id]?.intent)?repairGrant:'';
  async function inspect(){
    setBusy(true);onError('');
    try{setAssessment(await post({action:'delivery-assess',operation:action}));setView(await post({action:'delivery-view'}));}
    catch(error){setAssessment(null);onError(error.message);}finally{setBusy(false);}
  }
  async function load(){setView(await post({action:'delivery-view'}));await refreshOperations(false);}
  async function run(){
    setBusy(true);onError('');
    try{
      const grant=await post({action:'delivery-authorize',operation:action,binding:assessment.binding,operator,request:crypto.randomUUID(),...(action==='deliver'&&assessment.snapshot.profile.endpoint==='ci'&&selectedRepair.trim()?{attestation:{repair_grant:selectedRepair.trim()}}:{})});setLive(grant);
      setResult(await post({action:'delivery-run',grant:grant.id,request:crypto.randomUUID(),...(action==='repair'?{attestation:{repair_grant:selectedRepair}}:{})}));
      setAssessment(null);await load();
    }catch(error){onError(error.message);await load().catch(()=>{});}finally{setLive(null);setBusy(false);}
  }
  async function retained(request,row,repair=false){
    setBusy(true);onError('');
    try{setResult(await post({action:repair?'delivery-repair':'delivery-reconcile',grant:row.grant,request}));await load();}
    catch(error){onError(error.message);}finally{setBusy(false);}
  }
  async function cancel(grant){
    setCancelling(true);onError('');
    try{setResult(await post({action:'cancel',grant:grant.id,binding:grant.cancellation_binding,operator:grant.operator,request:crypto.randomUUID()}));}
    catch(error){onError(error.message);}finally{setCancelling(false);}
  }
  return <section aria-label="Reviewed delivery"><h3>Reviewed delivery</h3>
    <p>Deliver composes commit, branch publication, pull request and CI up to the configured endpoint. Each step uses the current accepted source and configured target. Branch publication, pull request, integration CI and merge remain distinct outcomes.</p>
    <label>Delivery action<select disabled={busy} value={action} onChange={event=>{setAction(event.target.value);setAssessment(null);}}>{['deliver','commit','branch','pr','ci','repair','merge'].map(value=><option key={value}>{value}</option>)}</select></label>
    <button disabled={busy} onClick={inspect}>Inspect delivery target</button>
    {assessment&&<div><p>Status: {assessment.status}. {assessment.blockers.join(', ')}</p><p>Repository: {assessment.snapshot.profile.repository}; push target: {assessment.snapshot.profile.remote_url}; branch: {assessment.snapshot.profile.branch}; base: {assessment.snapshot.profile.base} at {assessment.refs.base}; local revision: {assessment.head}.</p><p>Endpoint ceiling: {assessment.snapshot.profile.endpoint}. Merge policy: {assessment.snapshot.profile.merge_policy}.</p><details><summary>Intended files and required CI identities</summary><pre>{JSON.stringify({files:assessment.snapshot.files,checks:assessment.snapshot.profile.checks},null,2)}</pre></details>
      {(action==='repair'||(action==='deliver'&&assessment.snapshot.profile.endpoint==='ci'))&&<><label>Existing bounded factory grant{action==='deliver'?' (optional for CI repair)':''}<select disabled={busy} value={selectedRepair} onChange={event=>setRepairGrant(event.target.value)}><option value="">{action==='deliver'?'No automatic CI repair':'Select an existing allowance'}</option>{repairChoices.map(grant=>{const usage=operationsView.usage[grant.id]||{};const expired=grant.deadline*1000<=Date.now();const cancelled=!!operationsView.cancellations[grant.id]?.intent;return <option key={grant.id} value={grant.id} disabled={expired||cancelled}>{grant.operator}: {Math.max(0,grant.aggregate.calls-(usage.calls||0))} calls remaining; expires {new Date(grant.deadline*1000).toLocaleTimeString()}{expired?' (expired)':cancelled?' (cancelled)':''} [{grant.id.slice(-8)}]</option>;})}</select></label>{action==='deliver'&&<p>When supplied, this existing grant is bound to this delivery authorization. Eligible CI failure can use its remaining repair budget and deadline, then stops for fresh acceptance. It cannot accept or republish repaired source automatically.</p>}</>}
      <button disabled={busy||!operator.trim()||assessment.status!=='ready'||(action==='repair'&&!selectedRepair.trim())} onClick={run}>Authorize selected delivery action</button>
    </div>}
    {live&&<button disabled={cancelling} onClick={()=>cancel(live)}>Cancel active delivery</button>}
    {result&&<pre aria-label="Delivery result">{JSON.stringify(result,null,2)}</pre>}
    {view&&<details><summary>Retained delivery effects and reconciliation</summary>{Object.entries(view.state.compositions||{}).map(([request,row])=><div key={request}><p>Delivery endpoint: {row.status}.</p><button disabled={busy} onClick={()=>retained(request,row)}>Resume delivery endpoint {request}</button></div>)}{Object.entries(view.state.attempts).map(([request,row])=><div key={request}><p>{row.action}: {row.status}. {row.reason}</p><button disabled={busy} onClick={()=>retained(request,row)}>Reconcile delivery {request}</button>{row.repair&&<button disabled={busy} onClick={()=>retained(request,row,true)}>Resume retained CI repair {request}</button>}</div>)}{Object.values(view.state.grants).map(grant=><button key={grant.id} disabled={cancelling||!!view.cancellations[grant.id]?.intent} onClick={()=>cancel(grant)}>Cancel delivery grant {grant.id}</button>)}</details>}
  </section>;
}
