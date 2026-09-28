import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {existsSync,readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
const repo=resolve(dirname(fileURLToPath(import.meta.url)),'..'),root=process.env.NIGHTSHIFT_BROWSER_PROJECT,url=process.env.NIGHTSHIFT_BROWSER_URL;
const artifacts=process.env.NIGHTSHIFT_BROWSER_ARTIFACTS;mkdirSync(artifacts,{recursive:true});
const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
const intake=page.getByRole('region',{name:'Guided intake'}),operations=page.getByRole('region',{name:'Engineering operations'});
async function click(panel,label,action){const response=page.waitForResponse(r=>r.url().endsWith('/api/operations')&&r.request().postDataJSON()?.action===action,{timeout:120000});await panel.getByRole('button',{name:label,exact:true}).click();const r=await response;const value=await r.json();assert(r.ok(),JSON.stringify(value));return value;}
async function holdAction(action){
 let resume,entered;
 const gate=new Promise(resolve=>{resume=resolve;}),arrived=new Promise(resolve=>{entered=resolve;});
 await page.route('**/api/operations',async route=>{
  const request=route.request();
  if(request.method()==='POST'&&request.postDataJSON()?.action===action){entered();await gate;}
  await route.continue();
 });
 return {arrived,release:()=>resume()};
}
try{
 await page.goto(url);
 await operations.getByLabel('Task key',{exact:true}).fill('demo');
 await operations.getByRole('button',{name:'Assess operations',exact:true}).click();
 await operations.getByRole('button',{name:'Select factory recipe',exact:true}).waitFor();await intake.getByLabel('Source reference').fill('spec:request.md');
 const intakeHold=await holdAction('intake-preview');
 const pendingResponse=click(intake,'Preview request plan','intake-preview');await intakeHold.arrived;
 assert(await operations.getByLabel('Task key',{exact:true}).isDisabled(),'Intake must lock operation task switching');
 assert(await operations.getByRole('button',{name:'Select factory recipe',exact:true}).isDisabled(),'Intake must lock operation actions');
 intakeHold.release();const pending=await pendingResponse;assert.equal(pending.status,'needs_decision');assert.equal(pending.decision.continuation_operation,'none');
 assert(!existsSync(resolve(root,'.synthetic-calls.jsonl')));
 await page.reload();await intake.getByLabel('Source reference').fill('spec:request.md');
 const retained=await click(intake,'Preview request plan','intake-preview');assert.equal(retained.binding,pending.binding);assert.equal(retained.decision.sha256,pending.decision.sha256);
 await intake.getByLabel('Source files in scope, one per line').fill('app.py');await intake.getByLabel('Required behaviors, one per line').fill('Return two.');await intake.getByLabel('Existing test script').fill('test_app.py');await intake.getByLabel('Project rules file').fill('rules.md');await intake.getByLabel('Architecture context file').fill('architecture.md');
 const local=await click(intake,'Save choices and preview','intake-answer');assert.equal(local.status,'preview');
 const cli=JSON.parse(execFileSync('bash',[resolve(repo,'scripts/nightshift-factory.sh'),'intake','preview','--source','spec:request.md','--choices',JSON.stringify(local.options),'--project',root],{env:process.env,encoding:'utf8'}));assert.equal(cli.binding,local.binding);
 assert(!existsSync(resolve(root,'.synthetic-calls.jsonl')));await intake.getByLabel('Intake operator identity').fill('synthetic-browser');
 const cases=[];
 for(const source of ['spec:request.md','gh:synthetic/disposable#777']){
  let preview=local;
  if(source.startsWith('gh:')){await intake.getByLabel('Source reference').fill(source);preview=await click(intake,'Preview request plan','intake-preview');assert.equal(preview.source.repository,'synthetic/disposable');}
  const applyHold=await holdAction('intake-apply');
  const applying=click(intake,'Prepare inspected plan','intake-apply');await applyHold.arrived;
  assert(await operations.getByLabel('Task key',{exact:true}).isDisabled(),'Materialization must lock operation task switching');
  assert(await operations.getByRole('button',{name:'Assess operations',exact:true}).isDisabled(),'Materialization must lock operation assessment');
  applyHold.release();const applied=await applying;assert.equal(applied.status,'prepared');assert.equal(applied.provider_calls,0);
  const before=existsSync(resolve(root,'.synthetic-calls.jsonl'))?readFileSync(resolve(root,'.synthetic-calls.jsonl'),'utf8').trim().split('\n').length:0;
  assert.equal(before,cases.length*4);
  const assessment=page.waitForResponse(r=>r.url().includes('/api/operations?task='));await operations.getByRole('button',{name:'Assess operations',exact:true}).click();await assessment;
  await operations.getByLabel('Operator identity',{exact:true}).fill('synthetic-browser');await operations.getByRole('button',{name:'Select factory recipe',exact:true}).click();
  const operationHold=await holdAction('chain');
  const running=click(operations,'Authorize and run selected operations','chain');await operationHold.arrived;
  assert(await intake.getByLabel('Source reference').isDisabled(),'Operations must lock intake source switching');
  assert(await intake.getByRole('button',{name:'Preview request plan',exact:true}).isDisabled(),'Operations must lock intake preview');
  assert(await intake.getByLabel('Maximum provider calls').isDisabled(),'Operations must lock intake allowance changes');
  operationHold.release();const finished=await running;assert.equal(finished.view.status,'pending_manual_acceptance');
  const after=readFileSync(resolve(root,'.synthetic-calls.jsonl'),'utf8').trim().split('\n').length;assert.equal(after-before,4);
  cases.push({source,task:applied.task,binding:preview.binding,provider_calls:after-before,bidirectional_busy_assertions:true,usage:finished.view.usage});
 }
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'desktop horizontal overflow');
 await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile horizontal overflow');await page.screenshot({path:resolve(artifacts,'mobile.png'),fullPage:true});
 assert.equal(errors.length,0,errors.join('\n'));
 const requests=readFileSync(resolve(root,'.synthetic-calls.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
 const report={synthetic:true,browser:browser.version(),cases,provider_calls:requests.length,preview_provider_calls:0,requests,live_certification:false};writeFileSync(resolve(artifacts,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}finally{await browser.close();}
