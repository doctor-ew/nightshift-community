import assert from 'node:assert/strict';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {chromium} from 'playwright';
const root=path.dirname(fileURLToPath(import.meta.url)),evidence=path.resolve(root,'../test-output/recovery-progress-browser');
await mkdir(evidence,{recursive:true});
const ticket={task:'synthetic',settings:{ref:'spec:synthetic',provider:'codex',policy:'standard',auth:'subscription',push:false},running:false,finished:false,repair_remaining:0,progress:{phase:'No verified active worker'},pipeline:{status:'blocked',next_action:'product',attempts:[{stage:'product',status:'fail',reason:'Original retained failure'}],recovery_status:{status:'running',next_action:'adoption',allowance:{calls_used:1},steps:{verify:{status:'pass'},adoption:{status:'pending'}}}}};
const responses={'/api/intake':{view:{},token:'synthetic'},'/api/identity':{evidence_api:1,ticket_actions_api:2,ticket_chat_api:1},'/api/state':{root:'/synthetic/project',rows:[{ticket:'synthetic',source:'gate',state:'failed',reason:'Original retained failure'}],checkouts:[],ticket_usage:[],errors:[],warnings:[]},'/api/tickets':{tickets:[ticket],token:'synthetic'},'/api/workshop/reviews':{reviews:[],token:'synthetic'}};
const browser=await chromium.launch({headless:true}),errors=[],requests=[];
try{
 const page=await browser.newPage({viewport:{width:1280,height:1000}});page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url());requests.push({method:req.method(),path:url.pathname});assert.equal(url.origin,'http://nightshift-synthetic.invalid');assert.equal(req.method(),'GET');
  if(responses[url.pathname])return route.fulfill({json:responses[url.pathname]});
  const files={'/':'dist/index.html','/assets/app.js':'dist/assets/app.js','/assets/app.css':'dist/assets/app.css'};
  assert.ok(files[url.pathname],url.pathname);return route.fulfill({body:await readFile(path.join(root,files[url.pathname])),contentType:url.pathname.endsWith('.js')?'application/javascript':url.pathname.endsWith('.css')?'text/css':'text/html'});
 });
 await page.goto('http://nightshift-synthetic.invalid');
 const region=page.getByRole('region',{name:'Recorded recovery progress'});await region.waitFor();
 assert.match(await region.innerText(),/Recovery recorded · Adoption/);assert.match(await region.innerText(),/does not verify worker liveness/);assert.match(await region.innerText(),/Verification: pass/);assert.match(await region.innerText(),/Adoption: pending/);assert.match(await region.innerText(),/1 recovery calls recorded/);
 assert.match(await page.locator('.failure-summary').innerText(),/Original retained failure/);
 await page.screenshot({path:path.join(evidence,'recorded-desktop.png'),fullPage:true});
 // An unchanged record after a crash makes no new liveness claim.
 await page.reload();await region.waitFor();assert.match(await region.innerText(),/interrupted process can leave it unchanged/);
 ticket.pipeline.recovery_status.status='blocked';ticket.pipeline.recovery_status.reason='Unknown evidence reference <img src=x onerror="window.injected=true">';
 await page.reload();await region.waitFor();assert.match(await region.innerText(),/Recovery blocked/);assert.equal(await region.locator('img').count(),0);assert.equal(await page.evaluate(()=>window.injected),undefined);
 ticket.pipeline.recovery_status.status='pending_manual_acceptance';await page.reload();await region.waitFor();assert.match(await region.innerText(),/Manual acceptance pending/);
 ticket.pipeline.recovery_status.status='complete';ticket.pipeline.status='complete';await page.reload();await region.waitFor();assert.equal(await region.locator('h4').innerText(),'Complete');
 ticket.pipeline.status='stale';await page.reload();await region.waitFor();assert.match(await region.innerText(),/Changed evidence/);assert.match(await region.innerText(),/Verification: stale/);
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(evidence,'stale-mobile.png'),fullPage:true});
 assert.deepEqual(errors,[]);assert.equal(ticket.running,false);
 await writeFile(path.join(evidence,'report.json'),JSON.stringify({synthetic:true,provider_calls:0,requests,errors,checks:['recorded progress separate from worker liveness','unchanged crash record remains unverified','original failure retained','blocked reason text safe','manual acceptance separate','validated complete and stale priority','mobile no overflow','GET-only no controller action']},null,2)+'\n');
 console.log('PASS synthetic recorded recovery browser');
}finally{await browser.close();}
