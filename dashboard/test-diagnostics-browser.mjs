import assert from 'node:assert/strict';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {chromium} from 'playwright';
const root=path.dirname(fileURLToPath(import.meta.url));
const evidence=path.resolve(root,'../test-output/stage-diagnostics-browser');
await mkdir(evidence,{recursive:true});
const ticket={task:'1',settings:{ref:'gh:1',provider:'codex',policy:'standard',auth:'subscription',push:false},running:false,finished:false,repair_remaining:0,budget:{revision:'synthetic',calls_reserved:1,max_calls:5,unfinished:0,exhausted:true,wall_seconds_remaining:0,active_seconds_remaining:0,active_seconds:1,continuations:0},pipeline:{status:'blocked',next_action:'product',retry_budgets:{product:{next_action:'stop'}},attempts:[{stage:'product',status:'fail',reason:'stage_receipt.task:expected_string',diagnostic:{label:'UNVALIDATED_WORKER_DIAGNOSTIC',validation_error:'stage_receipt.task:expected_string',path:'synthetic/diagnostic.json',sha256:'a'.repeat(64),reported_findings:[{target:'extractor',problem:'External transfer needs approval. <img src=x onerror="window.untrustedExecuted=true">'}]}}]}};
const responses={
 '/api/intake':{view:{},token:'synthetic'},
 '/api/identity':{evidence_api:1,ticket_actions_api:2,ticket_chat_api:1},
 '/api/state':{root:'/synthetic/project',rows:[],checkouts:[],ticket_usage:[],errors:[],warnings:[]},
 '/api/tickets':{tickets:[ticket],token:'synthetic'},
 '/api/workshop/reviews':{reviews:[],token:'synthetic'},
};
const browser=await chromium.launch({headless:true});
const errors=[],requests=[];
try{
 const page=await browser.newPage({viewport:{width:1280,height:1000}});
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url());
  requests.push({method:request.method(),path:url.pathname});
  assert.equal(url.origin,'http://nightshift-synthetic.invalid');
  assert.equal(request.method(),'GET');
  if(responses[url.pathname])return route.fulfill({json:responses[url.pathname]});
  const files={'/':'dist/index.html','/assets/app.js':'dist/assets/app.js','/assets/app.css':'dist/assets/app.css'};
  if(files[url.pathname])return route.fulfill({body:await readFile(path.join(root,files[url.pathname])),contentType:url.pathname.endsWith('.js')?'application/javascript':url.pathname.endsWith('.css')?'text/css':'text/html'});
  throw new Error('Unexpected browser request '+url.pathname);
 });
 await page.goto('http://nightshift-synthetic.invalid');
 const diagnostic=page.getByRole('region',{name:'Unvalidated worker diagnostic'});
 await diagnostic.waitFor();
 assert.match(await diagnostic.innerText(),/External transfer needs approval/);
 assert.equal(await diagnostic.locator('img').count(),0);
 assert.equal(await page.evaluate(()=>window.untrustedExecuted),undefined);
 assert.equal(await page.getByRole('button',{name:'Grant 10 minutes & continue'}).isDisabled(),true);
 assert.equal(await page.getByRole('button',{name:'Resume',exact:true}).isDisabled(),true);
 await page.screenshot({path:path.join(evidence,'desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:path.join(evidence,'mobile.png'),fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
 assert.deepEqual(errors,[]);
 await writeFile(path.join(evidence,'report.json'),JSON.stringify({synthetic:true,provider_calls:0,requests,errors,checks:['unvalidated diagnostic visible','HTML-like diagnostic displayed as text','exhausted retry cannot grant time','mobile no horizontal overflow']},null,2)+'\n');
 console.log('PASS synthetic diagnostic browser');
}finally{await browser.close();}
