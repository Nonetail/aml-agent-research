import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const root = process.argv[2];
if (!root) throw new Error('Pass the absolute path of the pinned Meterless checkout');
const { Markovian } = await import(pathToFileURL(path.join(root, 'engines/markovian/reference/src/index.ts')));
const { WorldModel } = await import(pathToFileURL(path.join(root, 'engines/world-model/reference/src/index.ts')));

const results = {};
const historyDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aml-markovian-probe-'));
const prompts = [];
const states = [];
let historyExistsDuringSecondCall;
const engine = new Markovian({
  historyDir,
  chunkConfig: { maxChunks: 2, chunkSize: 2400, carryoverTokens: 128 },
});
const goal = 'Investigate this case. ' + 'x'.repeat(220) + ' MANDATORY_CUTOFF_2000_01_01';
const run = await engine.run({
  goal,
  reflect: false,
  attachments: [{ name: 'evidence', content: 'ROW_ID_123' }],
  generator: async (prompt, attachments) => {
    prompts.push(prompt);
    states.push({ attachments: attachments.length, promptLength: prompt.length });
    if (prompts.length === 1) return { text: 'work '.repeat(2500) + '\n[STATE_CHECKPOINT]\nCOMPLETED: checked X. REMAINING: check Y. CONTEXT: case-123.' };
    historyExistsDuringSecondCall = fs.existsSync(historyDir + '/history.json');
    return { text: 'candidate report [TASK_COMPLETE]' };
  },
});
assert.equal(run.status, 'completed');
assert.equal(run.chunks.length, 2);
results.markovian = {
  generatorCalls: prompts.length,
  configuredChunkSize: engine.config.chunkSize,
  firstChunkEstimatedOutputTokens: run.chunks[0].tokens,
  outputExceededConfiguredChunkSize: run.chunks[0].tokens > engine.config.chunkSize,
  historyExistsDuringSecondCall,
  historyExistsAfterRun: fs.existsSync(historyDir + '/history.json'),
  secondPromptContainsEndOfGoalConstraint: prompts[1].includes('MANDATORY_CUTOFF'),
  secondPromptContainsFullPriorOutput: prompts[1].includes('work '.repeat(100)),
  resumeMethodType: typeof engine.resume,
  states,
};

let toolMarkerCalls = 0;
const toolsRun = await new Markovian({chunkConfig: {maxChunks: 2}}).run({
  goal: 'Tool marker probe', reflect: false,
  generator: async () => {
    toolMarkerCalls++;
    return toolMarkerCalls === 1
      ? {text: 'Need query <NEEDS_TOOL tool="query" input="X"/>'}
      : {text: 'No actual tool was executed. [TASK_COMPLETE]'};
  },
});
results.toolMarker = { generatorCalls: toolMarkerCalls, finalStatus: toolsRun.status, chunks: toolsRun.chunks.length };

const world = new WorldModel({ namespace: 'probe', storage: 'memory' });
const source = {kind: 'fixture', at: '2000-01-01T00:00:00Z'};
const entities = await Promise.all(['A', 'B', 'C'].map(id => world.upsertEntity({
  type: 'account', externalKey: {system:'fixture', id}, name: id, source,
})));
await world.relate({from:entities[0].id, type:'transfers-to', to:entities[1].id, source});
await world.relate({from:entities[0].id, type:'transfers-to', to:entities[2].id, source:{...source, at:'2000-01-01T01:00:00Z'}});
const neighbors = world.view('graph').neighborsOf(entities[0].id, {via:'transfers-to'});
assert.deepEqual(neighbors.map(e => e.name), ['C']);
results.worldModel = {
  insertedRelationships: ['A->B', 'A->C'],
  currentNeighbors: neighbors.map(e=>e.name),
  explanation: 'A second open relationship with same from/type/context and different target closes the first in this reference.',
  buildPromptContextMethodType: typeof world.buildPromptContext,
};
console.log(JSON.stringify(results, null, 2));
