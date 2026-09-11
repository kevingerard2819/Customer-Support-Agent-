import { readFile, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const args = process.argv.slice(2);
const arg = (name) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : undefined; };
const read = async (path) => JSON.parse(await readFile(path, 'utf8'));
const dims = ['correctness', 'grounding', 'usefulness', 'routing_privacy'];

function weightedKappa(pairs) {
  if (pairs.length < 2) return null;
  const a = [0, 0, 0], b = [0, 0, 0];
  let observed = 0;
  for (const [x, y] of pairs) {
    a[x] += 1; b[y] += 1; observed += Math.abs(x - y) / 2;
  }
  observed /= pairs.length;
  let expected = 0;
  for (let x = 0; x < 3; x += 1) for (let y = 0; y < 3; y += 1) {
    expected += (a[x] / pairs.length) * (b[y] / pairs.length) * (Math.abs(x - y) / 2);
  }
  if (expected === 0) return null;
  return 1 - observed / expected;
}

function agreement(human, judge, ids) {
  const common = [...ids].filter((id) => human[id] && judge[id]).sort();
  const dimensions = {};
  for (const dim of dims) {
    const pairs = common.map((id) => [human[id][dim], judge[id][dim]])
      .filter(([a, b]) => [0, 1, 2].includes(a) && [0, 1, 2].includes(b));
    dimensions[dim] = {
      n: pairs.length,
      exact_agreement: pairs.length ? pairs.filter(([a, b]) => a === b).length / pairs.length : null,
      weighted_kappa: weightedKappa(pairs),
    };
  }
  const binary = common.filter((id) => typeof human[id].critical_failure === 'boolean' && typeof judge[id].critical_failure === 'boolean');
  const humanCritical = binary.filter((id) => human[id].critical_failure).length;
  const missed = binary.filter((id) => human[id].critical_failure && !judge[id].critical_failure).length;
  return {
    n_paired: common.length,
    dimensions,
    critical_failure_pairs: binary.length,
    critical_failure_exact_agreement: binary.length ? binary.filter((id) => human[id].critical_failure === judge[id].critical_failure).length / binary.length : null,
    judge_missed_human_critical_failures: missed,
    human_critical_failures: humanCritical,
    judge_critical_failure_recall: humanCritical ? (humanCritical - missed) / humanCritical : null,
  };
}

function overallPass(rating) {
  const values = dims.map((dim) => rating[dim]);
  return values.every((value) => [0, 1, 2].includes(value)) && !rating.critical_failure && !values.includes(0) && values.reduce((a, b) => a + b, 0) >= 6;
}

function summarize(ratings, key, partition) {
  const grouped = {};
  for (const [id, rating] of Object.entries(ratings)) {
    const identity = key[id];
    if (identity?.partition === partition) (grouped[identity.system] ??= []).push(rating);
  }
  return Object.fromEntries(Object.entries(grouped).sort().map(([system, rows]) => {
    const sum = (fn) => rows.reduce((total, row) => total + fn(row), 0);
    return [system, {
      n: rows.length,
      mean_scores: Object.fromEntries(dims.map((dim) => [dim, sum((row) => row[dim]) / rows.length])),
      overall_pass_count: sum((row) => Number(overallPass(row))),
      overall_pass_rate: sum((row) => Number(overallPass(row))) / rows.length,
      critical_failure_count: sum((row) => Number(row.critical_failure)),
      critical_failure_rate: sum((row) => Number(row.critical_failure)) / rows.length,
    }];
  }));
}

const packet = await read(resolve(arg('--packet') || join(root, 'annotations', 'reply-review-packet-v2.json')));
const humanDoc = await read(resolve(arg('--human') || join(root, 'annotations', 'reply-ratings-human-v2.json')));
const judgeDoc = await read(resolve(arg('--judge') || join(root, 'results', 'judge-mixed-3.5-3.8-v2', 'scores.json')));
const key = await read(resolve(arg('--key') || join(root, 'results', 'reply-review-key-v2.json')));
if (humanDoc.packet_id !== packet.packet_id || judgeDoc.packet_id !== packet.packet_id) throw new Error('Reply-review packet IDs do not match');
const human = humanDoc.ratings, judge = judgeDoc.scores;
const idsFor = (partition) => new Set(Object.entries(key).filter(([, row]) => row.partition === partition).map(([id]) => id));
const humanComplete = Object.keys(human).length === packet.items.length;
const judgeComplete = Object.keys(judge).length === packet.items.length;
const report = {
  packet_id: packet.packet_id,
  status: humanComplete && judgeComplete ? 'complete' : humanComplete && Object.keys(judge).length >= 60 ? 'complete_with_quota_limited_judge_subset' : 'incomplete',
  counts: { packet: packet.items.length, human: Object.keys(human).length, judge: Object.keys(judge).length },
  judge_model: judgeDoc.model,
  agreement: {
    calibration: agreement(human, judge, idsFor('calibration')),
    validation: agreement(human, judge, idsFor('validation')),
  },
  human_reply_quality: {
    calibration: summarize(human, key, 'calibration'),
    validation: summarize(human, key, 'validation'),
  },
  judge_reply_quality: {
    calibration: summarize(judge, key, 'calibration'),
    validation: summarize(judge, key, 'validation'),
  },
  method_note: `Humans rated all 90 blinded outputs: 30 calibration and 60 held-out validation. The Gemini judge completed ${Object.keys(judge).length}/90 before provider quota/capacity failures; the resulting paired subset contains ${[...idsFor('calibration')].filter((id) => judge[id]).length} calibration and ${[...idsFor('validation')].filter((id) => judge[id]).length} validation outputs. System identities were hidden during human scoring. The agent and judge use models from the Gemini family, so human ratings are primary; the incomplete judge subset and shared-family bias limit the agreement estimate.`,
};
await writeFile(join(root, 'results', 'reply-review-report-v2.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8');
console.log(JSON.stringify(report, null, 2));
if (report.status === 'incomplete') process.exitCode = 2;
