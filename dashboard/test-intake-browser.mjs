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
async function controlRoom() {
 // AC-1 AC-2 AC-3 AC-5: synthetic presentation fixtures; no operator testimony.
 let posts=[], polls=0;
 const long='recorded-model-'+ 'long-route-'.repeat(18);
 const fixture={task:'synthetic-control-room',sha256:'a'.repeat(64),settings:{branch:'auto',ref:'gh:synthetic/disposable#138',provider:'configured-must-not-leak',policy:'standard'},running:false,finished:false,
 pipeline:{status:'pending',next_action:'review',attempts:[
 {stage:'implement',status:'fail',reason:'Retained synthetic failure',route:{provider:'codex',model:'old-implementation-route'},receipt:'/tmp/'+ 'long-path/'.repeat(18)+'failure.json'},
 {stage:'implement',status:'pass',receipt:'/tmp/implementation-pass.json'},
 {stage:'review',status:'fail',reason:'Review synthetic failure',route:{provider:'claude',model:long},receipt:'/tmp/review-fail.json'}],completed:{implement:{receipt:'/tmp/implementation-pass.json'}}}};
 await page.route('**/api/tickets',route=>{polls++;return route.fulfill({json:{token:'synthetic-token',tickets:[fixture]}});});
 await page.route('**/api/tickets/*',route=>{posts.push(route.request().postDataJSON());return route.fulfill({json:{message:'synthetic saved'}});});
 await page.goto(url);
 const card=page.locator('.ticket-focus').filter({has:page.getByRole('heading',{name:fixture.task,exact:true})});
 await card.waitFor();
 assert(await card.evaluate(e=>!!(e.compareDocumentPosition(document.querySelector('[aria-label="Guided intake"]'))&Node.DOCUMENT_POSITION_FOLLOWING)),'Task precedes request setup');
 const nav=card.getByRole('navigation',{name:/stages/i});
 const buttons=nav.getByRole('button');assert.equal(await buttons.count(),6);
 const detail=card.getByRole('region',{name:/stage evidence/i});
 assert.equal(await nav.locator('[aria-pressed="true"]').count(),1);
 assert.match(await detail.innerText(),/Review synthetic failure/);
 for(const width of [1440,390]) {
  await page.setViewportSize({width,height:width===390?844:1000});
  for(let i=0;i<6;i++) {
   const b=buttons.nth(i);await b.focus();await page.keyboard.press(i%2?'Space':'Enter');
   assert.equal(await b.getAttribute('aria-pressed'),'true');assert.equal(await nav.locator('[aria-pressed="true"]').count(),1);
   assert(await b.evaluate(e=>e===document.activeElement));
   const box=await b.boundingBox();assert(box.height>=44,'Stage target at least 44px');
   assert(await b.evaluate(e=>getComputedStyle(e).outlineStyle!=='none'),'Visible focus');
  }
  await buttons.nth(2).click();
  const evidence=await detail.innerText();assert.match(evidence,/Retained synthetic failure/);assert(!evidence.includes(long));
  assert.match(evidence,/Provider not recorded/i);assert.match(evidence,/Model not recorded/i);
  assert.match(evidence,/Tests/i);assert.match(evidence,/Proof|receipt/i);
  assert(!evidence.includes('configured-must-not-leak'));
  await buttons.nth(5).click();assert.match(await detail.innerText(),/not recorded/i);assert(!(await detail.innerText()).includes('Retained synthetic failure'));
  await buttons.nth(3).focus();await page.keyboard.press('Enter');
  const initial=polls;await page.waitForFunction(()=>true);while(polls===initial) await page.waitForTimeout(100);
  assert.equal(await buttons.nth(3).getAttribute('aria-pressed'),'true');assert(await buttons.nth(3).evaluate(e=>document.activeElement===e));
  await page.keyboard.press('Tab');assert(await buttons.nth(4).evaluate(e=>document.activeElement===e));await page.keyboard.press('Shift+Tab');assert(await buttons.nth(3).evaluate(e=>document.activeElement===e));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal page overflow');
  const contrast=await card.evaluate(root=>{
   const rgb=s=>(s.match(/[\d.]+/g)||[]).map(Number);
   const lum=c=>c.slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
   const background=e=>{if(!e)return [0,0,0];const c=rgb(getComputedStyle(e).backgroundColor),base=background(e.parentElement),a=c.length>3?c[3]:1;return c.slice(0,3).map((v,i)=>v*a+base[i]*(1-a));};
   const ratio=(a,b)=>(Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
   const failures=[];
   for(const e of root.querySelectorAll('*')){if(!e.getClientRects().length)continue;const cs=getComputedStyle(e),bg=background(e);
    if([...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())){const large=parseFloat(cs.fontSize)>=24||(parseFloat(cs.fontSize)>=18.66&&parseInt(cs.fontWeight)>=700);if(ratio(rgb(cs.color),bg)<(large?3:4.5))failures.push(e.tagName+' text '+cs.color);}
    if(e.matches('button:not(:disabled)')){if(e.getBoundingClientRect().height<44)failures.push('action height');if(ratio(rgb(cs.borderTopColor),bg)<3)failures.push('control boundary '+cs.borderTopColor);}
   }return failures;
  });assert.deepEqual(contrast,[],'Computed contrast including composed backgrounds');
  await card.screenshot({path:resolve(artifacts,`control-room-${width}.png`)});
 }
 assert.equal(posts.length,0,'Inspection never dispatches');
 for(const state of ['complete','stale','pending_manual_acceptance','running','readonly','exhausted','unknown']) {
  fixture.pipeline.status=state==='readonly'||state==='exhausted'?'pending':state;
  fixture.pipeline.next_action=state==='unknown'?'unsupported-recorded-action':'review';
  fixture.running=state==='running';fixture.settings.branch=state==='readonly'?'none':'auto';fixture.finished=state==='complete';fixture.retry_exhausted_stage=state==='exhausted'?'review':null;
  await page.reload();await card.waitFor();
  if(['complete','running','readonly','exhausted'].includes(state))assert(await card.getByRole('button',{name:/^(Resume|Running|Run ended)$/,exact:true}).isDisabled());
  if(state==='unknown')assert.match(await card.innerText(),/unsupported-recorded-action/);
  assert.equal(posts.length,0);
 }
 fixture.task='synthetic-other-task';fixture.pipeline={status:'pending',next_action:'product',attempts:[]};await page.reload();
 assert(!(await page.getByRole('region',{name:/stage evidence/i}).innerText()).includes('Review synthetic failure'));
 await page.unroute('**/api/tickets');await page.unroute('**/api/tickets/*');
 writeFileSync(resolve(artifacts,'control-room-report.json'),JSON.stringify({synthetic:true,widths:[1440,390],inspection_posts:posts,checks:['stage isolation','keyboard/focus/polling','missing routes','history','computed contrast','44px controls','overflow','admission states'],manual_acceptance:'pending'},null,2));
}
try{
 await controlRoom();
 await page.setViewportSize({width:1440,height:1000});
 await page.goto(url);
 assert(!(await intake.locator('.intake-options').evaluate(el=>el.open)),'Detailed request fields start collapsed');
 assert(!(await intake.locator('.intake-runtime').evaluate(el=>el.open)),'Runtime diagnostics start collapsed');
 assert(await intake.getByLabel('Source reference').isVisible(),'Source reference stays available');
 await operations.getByLabel('Task key',{exact:true}).fill('demo');
 await operations.getByRole('button',{name:'Assess operations',exact:true}).click();
 await operations.getByRole('button',{name:'Select factory recipe',exact:true}).waitFor();await intake.getByLabel('Source reference').fill('spec:request.md');
 const intakeHold=await holdAction('intake-preview');
 const pendingResponse=click(intake,'Preview request plan','intake-preview');await intakeHold.arrived;
 assert(await operations.getByLabel('Task key',{exact:true}).isDisabled(),'Intake must lock operation task switching');
 assert(await operations.getByRole('button',{name:'Select factory recipe',exact:true}).isDisabled(),'Intake must lock operation actions');
 intakeHold.release();const pending=await pendingResponse;assert.equal(pending.status,'needs_decision');assert(await intake.locator('.intake-options').evaluate(el=>el.open),'Missing choices reveal detailed controls');assert.equal(pending.decision.continuation_operation,'none');
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
