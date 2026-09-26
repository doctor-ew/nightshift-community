import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {existsSync,readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
const repo=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const root=process.env.NIGHTSHIFT_BROWSER_PROJECT,url=process.env.NIGHTSHIFT_BROWSER_URL,reference=process.env.NIGHTSHIFT_INTAKE_REFERENCE;
assert(root&&url&&reference);
const output=resolve(repo,'test-output/intake-browser',reference.startsWith('gh:')?'github':'local');mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1100}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const panel=page.getByRole('region',{name:'Start new work'}),operations=page.getByRole('region',{name:'Engineering operations'});
async function click(name,action){
 const response=page.waitForResponse(r=>r.url().endsWith('/api/intake')&&r.request().postDataJSON()?.action===action);
 await panel.getByRole('button',{name,exact:true}).click();const r=await response;const value=await r.json();assert.equal(r.status(),200,JSON.stringify(value));return value;
}
try {
 await page.goto(url);await panel.getByLabel('Source reference').fill(reference);
 let value=await click('Resolve source','resolve');const task=value.task;
 await panel.getByLabel('Files to change (one path per line)').fill('app.py');
 await panel.getByLabel('Project rules file').fill('rules.md');await panel.getByLabel('Architecture guidance file').fill('architecture.md');
 await panel.getByLabel('Verification script').fill('test_app.py');await panel.getByLabel('Required acceptance behavior').fill('Return two.');
 value=await click('Prepare inspectable draft','draft');assert.equal(value.status,'draft');
 assert(!existsSync(resolve(root,'.synthetic-calls.jsonl')));
 value=await click('Create draft files','materialize');assert.equal(value.status,'materialized');assert(!existsSync(resolve(root,'.synthetic-calls.jsonl')));
 const cli=JSON.parse(execFileSync('bash',[resolve(repo,'scripts/nightshift-factory.sh'),'intake','--project',root,'--request','-'],{env:process.env,input:JSON.stringify({action:'view',task}),encoding:'utf8'}));
 assert.deepEqual(cli.operations,value.operations);
 await operations.getByLabel('Operator identity').fill('synthetic-intake-browser');
 await operations.getByRole('button',{name:'Select factory recipe',exact:true}).click();
 const resultResponse=page.waitForResponse(r=>r.url().endsWith('/api/operations')&&r.request().postDataJSON()?.action==='chain',{timeout:120000});
 await operations.getByRole('button',{name:'Authorize and run selected operations',exact:true}).click();
 const result=await(await resultResponse).json();assert.equal(result.view.status,'pending_manual_acceptance',JSON.stringify(result));
 const before=readFileSync(resolve(root,'.synthetic-calls.jsonl'),'utf8');assert.equal(before.trim().split('\n').length,4);
 await operations.getByText('Retained authorizations and recovery',{exact:true}).click();
 const replayResponse=page.waitForResponse(r=>r.url().endsWith('/api/operations')&&r.request().postDataJSON()?.action==='chain');
 await operations.getByRole('button',{name:/^Resume /}).click();const replay=await(await replayResponse).json();
 assert.equal(readFileSync(resolve(root,'.synthetic-calls.jsonl'),'utf8'),before);
 assert.deepEqual(errors,[]);await page.screenshot({path:resolve(output,'intake.png'),fullPage:true});
 const report={synthetic:true,reference,browser:browser.version(),provider_calls:4,replay_calls:0,replayed_operation_receipts:replay.results.length,requests:before.trim().split('\n').map(JSON.parse),usage:result.view.usage,tokens:null,provider_kv_cache_reuse:null,billed_cost:null,live_certification:false};
 writeFileSync(resolve(output,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}finally{await browser.close();}
