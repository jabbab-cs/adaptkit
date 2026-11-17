// Checks the JavaScript runtime against adaptkit/spec/test_vectors.json
// (expected values come from the Python reference implementation).
// Run from the project root:  node --test adaptkit/js/test/

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  indexOfDifficulty, windowFeatures, binValue, stateKey, decide, applyAction, toCSV, EVENT_COLUMNS,
} from '../adaptkit.js';

const vectors = JSON.parse(readFileSync(new URL('../../spec/test_vectors.json', import.meta.url), 'utf8'));
const { policy, tolerance } = vectors;

function assertClose(actual, expected, label) {
  if (expected === null) {
    assert.equal(actual, null, `${label}: expected null, got ${actual}`);
    return;
  }
  assert.ok(actual !== null && Math.abs(actual - expected) <= tolerance, `${label}: expected ${expected}, got ${actual}`);
}

test('index of difficulty', () => {
  for (const v of vectors.index_of_difficulty) {
    assertClose(indexOfDifficulty(v.amplitude, v.target_w), v.expected, `ID(${v.amplitude}, ${v.target_w})`);
  }
});

test('binning', () => {
  for (const v of vectors.bins) {
    assert.equal(binValue(v.value, v.thresholds), v.expected, `bin(${v.value}, ${v.thresholds})`);
  }
});

for (const c of vectors.cases) {
  test(`features and state: ${c.name}`, () => {
    const f = windowFeatures(c.events, policy);
    for (const k of Object.keys(c.expected.features)) assertClose(f[k], c.expected.features[k], `${c.name}.${k}`);
    const device = c.events.length ? c.events[c.events.length - 1].device : 'mouse';
    assert.equal(stateKey(f, c.ui, device, policy), c.expected.state);
  });
}

for (const d of vectors.decisions) {
  test(`decision: ${d.name}`, () => {
    const c = vectors.cases.find((x) => x.name === d.case);
    const res = decide(c.events, c.ui, { eventsSeen: d.ctx.events_seen, undone: new Set(d.ctx.undone) }, policy);
    assert.equal(res.state, d.expected.state);
    assert.equal(res.proposed, d.expected.proposed);
    assert.equal(res.action, d.expected.action);
    assert.deepEqual(applyAction(c.ui, res.action, policy), d.expected.ui_after);
  });
}

test('CSV export has every schema column and escapes commas', () => {
  const csv = toCSV([{ participant: 'P,1', hit: 1, time_ms: 500 }]);
  const [header, row] = csv.trim().split('\n');
  assert.equal(header, EVENT_COLUMNS.join(','));
  assert.ok(row.includes('"P,1"'));
});

test('runtime columns match the event schema', () => {
  const schema = JSON.parse(readFileSync(new URL('../../spec/events.schema.json', import.meta.url), 'utf8'));
  assert.deepEqual([...EVENT_COLUMNS].sort(), Object.keys(schema.properties).sort());
});
