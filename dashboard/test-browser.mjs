import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {resolve, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const root=process.env.NIGHTSHIFT_BROWSER_PROJECT, url=process.env.NIGHTSHIFT_BROWSER_URL;
assert(root && url, 'Use npm run test:browser to prepare isolated fixtures');
const repo=resolve(dirname(fileURLToPath(import.meta.url)), '..');
const artifacts=resolve(process.env.NIGHTSHIFT_BROWSER_ARTIFACTS || resolve(repo,'test-output/browser'));
mkdirSync(artifacts,{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
page.on('response',r=>{if(r.url().endsWith('/api/operations')) console.log('operation',r.request().postDataJSON()?.action,r.status());});
const cli=(...args)=>JSON.parse(execFileSync('bash',[resolve(repo,'scripts/nightshift-factory.sh'),'ops',...args,'--project',root],{env:process.env,encoding:'utf8'}));
const calls=()=>readFileSync(resolve(root,'.synthetic-calls.jsonl'),'utf8').trim().split('\n').length;
const panel=page.getByRole('region',{name:'Engineering operations'});
async function assess(){
  const response=page.waitForResponse(r=>r.url().includes('/api/operations?task='));
  await panel.getByRole('button',{name:'Assess operations',exact:true}).click();
  const value=await (await response).json();
  await panel.getByRole('button',{name:'Assess operations',exact:true}).waitFor({state:'visible'});
  await page.waitForFunction(()=>!document.querySelector('[aria-label="Engineering operations"] input').disabled);
  return value.view;
}
async function execute(action='chain'){
  const response=page.waitForResponse(r=>r.url().endsWith('/api/operations') && r.request().postDataJSON()?.action===action,{timeout:90000});
  await panel.getByRole('button',{name:'Authorize and run selected operations',exact:true}).click();
  const value=await (await response).json();
  await page.waitForFunction(()=>!document.querySelector('[aria-label="Engineering operations"] input').disabled);
  return value;
}
function sameView(a,b){delete a.usage;delete b.usage;assert.deepEqual(a,b);}
try {
  await page.goto(url);
  await panel.getByLabel('Task key').fill('demo');
  let view=await assess();sameView(view,cli('view','demo'));
  assert(await panel.getByRole('button',{name:'Select implement',exact:true}).isDisabled());
  await panel.getByLabel('Operator identity').fill('synthetic-browser-operator');
  await panel.getByRole('button',{name:'Select factory recipe',exact:true}).click();
  let result=await execute();assert.equal(result.view.status,'pending_manual_acceptance');assert.equal(calls(),4);
  const originalResults=structuredClone(result.results),initialUsage=structuredClone(result.view.usage);
  const typed=process.env.NIGHTSHIFT_TYPED_BROWSER==='1';
  if(typed){const observation=result.view.operations.find(r=>r.operation==='verify').result.observations[0];assert.equal(observation.adapter,'unittest-v1');assert.equal(observation.typed.status,'passed');assert.equal(observation.typed.counts.passed,1);assert.equal(observation.typed.receipt.complete,true);}
  sameView(await assess(),cli('view','demo'));
  await panel.screenshot({path:resolve(artifacts,'operations-pending-acceptance.png')});
  await panel.getByText('Retained authorizations and recovery',{exact:true}).click();
  const replay=page.waitForResponse(r=>r.url().endsWith('/api/operations') && r.request().postDataJSON()?.action==='chain');
  await panel.getByRole('button',{name:/^Resume /}).first().click();
  result=await (await replay).json();assert.deepEqual(result.results.map(({next_action,...receipt})=>receipt),originalResults.map(({next_action,...receipt})=>receipt));assert.equal(calls(),4);
  await page.waitForFunction(()=>!document.querySelector('[aria-label="Engineering operations"] input').disabled);
  await panel.getByText('Retained authorizations and recovery',{exact:true}).click();
  await panel.getByRole('button',{name:'Select factory recipe',exact:true}).click();
  await panel.getByLabel('Repair eligible failures within this allowance').check();
  result=await execute('supervise');assert.equal(result.status,'passed');assert.equal(calls(),4);
  sameView(await assess(),cli('view','demo'));
  await panel.getByRole('button',{name:'Select accept',exact:true}).click();
  assert(await panel.getByRole('button',{name:'Authorize and run selected operations',exact:true}).isDisabled());
  await panel.getByRole('checkbox').check();result=await execute();assert.equal(result.results[0].status,'passed');assert.equal(calls(),4);
  // Source drift must remove approval; explicit external adoption cannot repeat Implement.
  writeFileSync(resolve(root,'app.py'),'def answer():\n    return 3\n');
  view=await assess();assert.notEqual(view.operations.find(r=>r.operation==='accept').status,'current');
  await panel.getByRole('button',{name:'Select adopt',exact:true}).click();
  await panel.getByLabel('External author identity').fill('synthetic-external-author');
  await panel.getByLabel('Actual author provider').selectOption('human');
  result=await execute();assert.equal(result.results[0].status,'passed');assert.equal(calls(),4);
  await panel.getByRole('button',{name:'Select verify',exact:true}).click();
  result=await execute();assert.equal(result.results[0].status,'failed');assert.equal(calls(),4);
  assert((await panel.getByRole('alert').innerText()).length>0);
  assert(await panel.getByRole('button',{name:'Select review',exact:true}).isDisabled());
  sameView(await assess(),cli('view','demo'));
  await panel.getByRole('button',{name:'Select verify',exact:true}).scrollIntoViewIfNeeded();
  await panel.screenshot({path:resolve(artifacts,'operations-failed-verification.png')});
  await page.reload();await panel.getByLabel('Task key').fill('demo');view=await assess();
  assert.equal(view.operations.find(r=>r.operation==='verify').status,'blocked');
  assert(view.attempts.some(r=>r.operation==='verify' && r.status==='failed'));
  assert(view.operations.find(r=>r.operation==='verify').findings.length>0);
  await page.setViewportSize({width:390,height:844});
  await panel.getByRole('button',{name:'Select verify',exact:true}).scrollIntoViewIfNeeded();
  await panel.screenshot({path:resolve(artifacts,'operations-mobile.png')});
  assert(await panel.evaluate(e=>e.scrollWidth<=e.clientWidth+1),'Operation panel overflows mobile viewport');
  assert.deepEqual(errors,[]);
  const report={synthetic:true,typed,browser:browser.version(),provider_calls:calls(),replay_provider_calls:0,usage:initialUsage,requests:readFileSync(resolve(root,'.synthetic-calls.jsonl'),'utf8').trim().split('\n').map(JSON.parse),provider_tokens:null,provider_cache_usage:null,billed_cost:null,checks:['UI/CLI admission parity','factory recipe','explicit bounded supervisor without redispatch','manual acceptance required','duplicate resume without dispatch','explicit acceptance','source drift','external adoption without implementation','failed verification remains failed','blocked review','reload persistence','desktop/mobile rendering without script errors'],live_certification:false};
  writeFileSync(resolve(artifacts,'report.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report));
} catch(error) {
  await page.screenshot({path:resolve(artifacts,'failure.png'),fullPage:true});
  console.error(await panel.innerText());
  throw error;
} finally {await browser.close();}
