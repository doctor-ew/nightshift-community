// Trusted Node runner events; printed test output is never a count source.
import {writeFileSync,renameSync} from 'node:fs';
const path=process.env.NIGHTSHIFT_TEST_EVENTS,binding=process.env.NIGHTSHIFT_TEST_BINDING;
export default async function* (source){
 const report={version:1,adapter:'node-test-v1',binding,runtime:process.version,complete:false,runs:[],success:false};
 const save=()=>{const text=JSON.stringify(report);if(Buffer.byteLength(text)>1000000)throw Error('verification_events_too_large');writeFileSync(path+'.tmp',text);renameSync(path+'.tmp',path);};
 save();let final=false;
 for await(const event of source){
  if(event.type==='test:stdout'||event.type==='test:stderr')yield event.data.message;
  if(event.type==='test:summary'){
   const c=event.data.counts;
   if(event.data.file)report.runs.push({complete:true,counts:{total:c.tests,passed:c.passed,failed:c.failed,errors:c.cancelled,skipped:c.skipped,expected_failures:c.todo,unexpected_successes:0}});
   else {final=true;report.success=event.data.success;}
   yield JSON.stringify({event:event.type,data:event.data})+'\n';save();
  }
 }
 report.complete=final;save();
}
