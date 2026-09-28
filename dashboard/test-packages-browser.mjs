import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
const repo=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const root=process.env.NIGHTSHIFT_BROWSER_PROJECT,url=process.env.NIGHTSHIFT_BROWSER_URL;
assert(root&&url);
const artifacts=resolve(process.env.NIGHTSHIFT_BROWSER_ARTIFACTS||resolve(repo,'test-output/packages-browser'));
mkdirSync(artifacts,{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const panel=page.getByRole('region',{name:'Engineering operations'});
const cli=()=>JSON.parse(execFileSync('bash',[resolve(repo,'scripts/nightshift-factory.sh'),'packages','view','--task','demo','--project',root],{env:process.env,encoding:'utf8'}));
async function click(name,action){
 const response=page.waitForResponse(r=>r.url().endsWith('/api/operations')&&r.request().postDataJSON()?.action===action,{timeout:120000});
 await panel.getByRole('button',{name,exact:true}).click();
 const value=await(await response).json();
 await page.waitForFunction(()=>!document.querySelector('[aria-label="Engineering operations"] input').disabled);
 return value;
}
try{
 await page.goto(url);await panel.getByLabel('Task key').fill('demo');
 const admission=page.waitForResponse(r=>r.url().includes('/api/operations?task='));
 await panel.getByRole('button',{name:'Assess operations',exact:true}).click();await admission;
 await panel.getByLabel('Operator identity').fill('synthetic-package-browser');
 let value=await click('Inspect work packages','packages-view');assert.equal(value.assessment.status,'blocked');
 assert(await panel.getByRole('button',{name:'Authorize bounded package composition',exact:true}).isDisabled());
 value=await click('Authorize decomposition preparation and challenge','packages-prepare');assert.equal(value.status,'ready');
 value=await click('Authorize bounded package composition','packages-run');assert.equal(value.status,'pending_manual_acceptance');assert.equal(value.usage.calls,14);
 const before=readFileSync(resolve(root,'.synthetic-calls.jsonl'),'utf8');
 const retained=cli();assert.deepEqual(retained.usage[value.grant.id],value.usage);
 value=await click('Resume package grant '+value.grant.id,'packages-run');assert.equal(value.status,'pending_manual_acceptance');
 assert.equal(readFileSync(resolve(root,'.synthetic-calls.jsonl'),'utf8'),before);
 await page.screenshot({path:resolve(artifacts,'packages.png'),fullPage:true});
 assert.deepEqual(errors,[]);
 const report={synthetic:true,browser:browser.version(),provider_calls:14,replay_calls:0,requests:before.trim().split('\n').map(JSON.parse),usage:value.usage,live_certification:false};
 writeFileSync(resolve(artifacts,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}finally{await browser.close();}
