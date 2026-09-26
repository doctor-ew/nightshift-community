import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {resolve} from 'node:path';
import {chromium} from 'playwright';
const root=process.env.NIGHTSHIFT_BROWSER_PROJECT,url=process.env.NIGHTSHIFT_BROWSER_URL,artifacts=process.env.NIGHTSHIFT_DELIVERY_BROWSER_ARTIFACTS;
const repairGrant=process.env.NIGHTSHIFT_DELIVERY_BROWSER_REPAIR_GRANT;
assert(root&&url&&artifacts,'Use the disposable delivery browser fixture');
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
page.on('pageerror',error=>errors.push(error.message));
const panel=page.getByRole('region',{name:'Engineering operations'}),delivery=page.getByRole('region',{name:'Reviewed delivery'});
const calls=()=>readFileSync(resolve(root,'.synthetic-calls.jsonl'),'utf8').trim().split('\n').length;
const head=()=>execFileSync('git',['-C',root,'rev-parse','HEAD'],{encoding:'utf8'}).trim();
const idle=()=>page.waitForFunction(()=>!document.querySelector('[aria-label="Engineering operations"] input').disabled);
async function response(action,click){const pending=page.waitForResponse(r=>r.url().endsWith('/api/operations')&&r.request().postDataJSON()?.action===action,{timeout:120000});await click();const raw=await pending,value=await raw.json();assert(raw.ok(),JSON.stringify(value));await idle();return value;}
async function accept(){await panel.getByRole('button',{name:'Select accept',exact:true}).click();await panel.getByLabel('I accept this exact reviewed evidence and the recorded case observations.',{exact:true}).check();const accepted=await response('chain',()=>panel.getByRole('button',{name:'Authorize and run selected operations',exact:true}).click());assert.equal(accepted.results[0].status,'passed');}
async function inspect(){return response('delivery-assess',()=>delivery.getByRole('button',{name:'Inspect delivery target',exact:true}).click());}
try{
 await page.goto(url);await panel.getByLabel('Task key').fill('demo');
 const pending=page.waitForResponse(r=>r.url().includes('/api/operations?task='));await panel.getByRole('button',{name:'Assess operations',exact:true}).click();await pending;await idle();
 await panel.getByLabel('Operator identity').fill('synthetic-delivery-browser');await accept();assert.equal(calls(),4);
 await delivery.getByLabel('Delivery action').selectOption('deliver');
 const assessed=await inspect();assert.equal(assessed.snapshot.profile.endpoint,'ci');assert.equal(assessed.snapshot.profile.merge_policy,'disabled');assert.equal(assessed.status,'ready');
 assert(await delivery.getByText(/Repository: synthetic\/repository/).isVisible());
 if(repairGrant)await delivery.getByLabel('Existing bounded factory grant').selectOption(repairGrant);
 const first=await response('delivery-run',()=>delivery.getByRole('button',{name:'Authorize selected delivery action',exact:true}).click());
 const initialHead=first.results[0].head;
 assert.equal(first.status,repairGrant?'needs_acceptance':'ci_passed');assert.deepEqual(first.results.map(r=>r.status),['commit_prepared','branch_published','pr_open',repairGrant?'ci_failed':'ci_passed']);assert.equal(calls(),repairGrant?6:4);
 assert.equal(head(),initialHead,'repair must not commit or republish without fresh acceptance');
 await delivery.getByText('Retained delivery effects and reconciliation',{exact:true}).click();
 const replay=await response('delivery-reconcile',()=>delivery.getByRole('button',{name:/^Resume delivery endpoint /}).first().click());assert.equal(replay.status,first.status);assert.equal(calls(),repairGrant?6:4);assert.equal(head(),initialHead);
 let final=first;
 if(repairGrant){
  await accept();assert.equal(calls(),6);await inspect();await delivery.getByLabel('Existing bounded factory grant').selectOption('');
  final=await response('delivery-run',()=>delivery.getByRole('button',{name:'Authorize selected delivery action',exact:true}).click());assert.equal(final.status,'ci_passed');assert.notEqual(head(),initialHead);assert.equal(calls(),6);
 }
 await page.screenshot({path:resolve(artifacts,'delivery-ci-passed.png'),fullPage:true});
 await page.reload();await panel.getByLabel('Task key').fill('demo');
 const refreshed=page.waitForResponse(r=>r.url().includes('/api/operations?task='));await panel.getByRole('button',{name:'Assess operations',exact:true}).click();await refreshed;await idle();
 await delivery.getByLabel('Delivery action').selectOption('merge');
 const blocked=await inspect();assert.equal(blocked.status,'blocked');assert(blocked.blockers.includes('merge_not_enabled'));
 assert(await delivery.getByRole('button',{name:'Authorize selected delivery action',exact:true}).isDisabled());
 await page.setViewportSize({width:390,height:844});assert(await delivery.isVisible());assert.deepEqual(errors,[]);
 writeFileSync(resolve(artifacts,'browser.json'),JSON.stringify({browser:browser.version(),initial_head:initialHead,final_head:head(),repair_worker_calls:repairGrant?2:0,replay_provider_calls:0,reused_delivery_steps:replay.results.length,endpoint:final.status,checks:['rendered bound acceptance','rendered endpoint composition','real local Git publication','synthetic PR and integration CI transport',...(repairGrant?['explicit existing repair grant bound in UI','CI failure repair followed by Verify and independent Review','needs acceptance without automatic commit or push','fresh rendered acceptance and newly authorized delivery']:[]),'retained composition replay','reload and blocked merge','desktop/mobile no script errors']}));
}catch(error){await page.screenshot({path:resolve(artifacts,'delivery-failure.png'),fullPage:true});writeFileSync(resolve(artifacts,'failure.html'),await page.content());throw error;}finally{await browser.close();}
