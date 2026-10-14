import assert from 'node:assert/strict';
import {chromium} from 'playwright';

const url=process.env.NIGHTSHIFT_READ_ONLY_URL;
assert(url, 'Run through tests/test-console-read-only-browser.py');
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];page.on('pageerror', error=>errors.push(error.message));
try {
  await page.goto(url);
  const panel=page.getByRole('region',{name:'Ticket status'});
  const ticket=panel.locator('article').filter({has:page.getByRole('heading',{name:'demo',exact:true})});
  await ticket.waitFor();
  assert(await ticket.getByRole('status').filter({hasText:/^Read-only controller run\. Resume from the terminal with the recorded policy\.$/}).isVisible());
  assert(await ticket.getByRole('button',{name:'Resume',exact:true}).isDisabled());
  assert(await ticket.getByRole('button',{name:'Diagnose & repair',exact:true}).isDisabled());
  assert(await ticket.getByRole('button',{name:'Grant 10 minutes & continue',exact:true}).isDisabled());
  await ticket.getByText('Recovery options',{exact:true}).click();
  assert(await ticket.getByRole('button',{name:'Prepare to resume',exact:true}).isDisabled());
  await ticket.getByText('Controller routing and receipts',{exact:true}).click();
  assert(await ticket.getByText('Recorded state: blocked. Next stage or action: product.',{exact:true}).isVisible());
  assert(await ticket.getByText('Synthetic transport failed',{exact:false}).isVisible());
  assert(await ticket.getByText('codex · synthetic-model · infrastructure',{exact:true}).isVisible());
  assert(await ticket.getByText('Receipt:',{exact:false}).isVisible());
  await page.screenshot({path:process.env.NIGHTSHIFT_READ_ONLY_ARTIFACTS + '/desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:process.env.NIGHTSHIFT_READ_ONLY_ARTIFACTS + '/mobile.png',fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth), 'Mobile layout overflow');
  assert.deepEqual(errors,[]);
  console.log('Read-only ticket browser checks passed; desktop/mobile screenshots saved.');
} finally { await browser.close(); }
