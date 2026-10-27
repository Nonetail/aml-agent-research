// Real pinned Markovian engine; each generator invokes one durable Python segment.
import {spawn} from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const directory=process.argv[2];
if (!directory) throw new Error('Pass a new run directory');
const source=path.join(here,'generated/meterless-source');
const {Markovian}=await import(pathToFileURL(path.join(source,'engines/markovian/reference/src/index.ts')));
async function command(action,input={}) {
  const result=await new Promise((resolve,reject)=>{
    const child=spawn('python3',[path.join(here,'chunk_case.py'),action,directory,...(action==='init'?process.argv.slice(3):[])],{stdio:['pipe','pipe','pipe']});
    let stdout='',stderr='';
    child.stdout.on('data',b=>stdout+=b); child.stderr.on('data',b=>stderr+=b);
    child.on('error',reject);
    child.on('close',code=>code===0 ? resolve(JSON.parse(stdout)) : reject(new Error(`Segment failed (${code}): ${stderr}`)));
    child.stdin.end(JSON.stringify(input));
  });
  console.log(JSON.stringify({phase:action,result}));
  return result;
}
await command('init');
let session=0;
while(JSON.parse(await fs.readFile(path.join(directory,'state.json'),'utf8')).status==='active') {
  session++;
  const engine=new Markovian({historyDir:path.join(directory,`meterless-history-${session}`),chunkConfig:{maxChunks:32,chunkSize:2400,carryoverTokens:512}});
  const result=await engine.run({
    goal:'Continue the saved AML case until its frontier is exhausted or its case budget pauses execution. Fresh contexts preserve exact evidence and pending cursors in the durable case. Cutoff is 2022/09/11 00:00. Never access evaluator labels.',
    reflect:false,
    generator:async prompt=>{
      const step=await command('segment',{engine_prompt:prompt});
      const done=step.status!=='active';
      return {text:`Chunk ${step.chunk}: ${step.stored_rows} stored rows, ${step.pending_scopes} unfinished scopes. Case status: ${step.status}. ${done?'[TASK_COMPLETE]':''}\n[STATE_CHECKPOINT]\n${JSON.stringify(step.checkpoint)}`};
    },
  });
  await fs.writeFile(path.join(directory,`meterless-result-${session}.json`),JSON.stringify(result,null,2));
  if(!['completed','max-chunks'].includes(result.status)) throw new Error(`Markovian stopped: ${result.status}: ${result.error||''}`);
}
const finalState=JSON.parse(await fs.readFile(path.join(directory,'state.json'),'utf8'));
if(finalState.status==='frontier_exhausted') await command('review');
await command('audit');
