"""Build component-disjoint annotation and retrieval subsets from the original archive.

No future support text is exported in the annotation packet. Standard library only.
"""
import argparse
from array import array
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import html
import json
from pathlib import Path
import random
import re
from inspect_data import rows


class Components:
    def __init__(self):
        self.parent = array('I', [0])

    def ensure(self, n):
        if n >= len(self.parent):
            self.parent.extend(range(len(self.parent), n + 1))

    def find(self, n):
        while self.parent[n] != n:
            self.parent[n] = self.parent[self.parent[n]]
            n = self.parent[n]
        return n

    def union(self, a, b):
        self.ensure(max(a, b))
        a, b = self.find(a), self.find(b)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def normalized(text):
    text = html.unescape(text).casefold()
    text = re.sub(r'https?://\S+|@[\w_]+', ' ', text)
    return ' '.join(re.findall(r'\w+', text))


def features(text):
    tokens = normalized(text).split()
    if len(tokens) < 4:
        return frozenset(['short:' + ' '.join(tokens)])
    return frozenset(' '.join(tokens[i:i+3]) for i in range(len(tokens)-2))


class SimilarityIndex:
    def __init__(self):
        self.postings = defaultdict(set)
        self.sets = []

    def similar(self, text):
        f = features(text)
        candidates = set()
        for token in f:
            candidates.update(self.postings[token])
        return any(len(f & self.sets[i]) / len(f | self.sets[i]) >= .8 for i in candidates)

    def add(self, text):
        f = features(text)
        i = len(self.sets)
        self.sets.append(f)
        for token in f:
            self.postings[token].add(i)


def timestamp(row):
    return datetime.strptime(row['created_at'], '%a %b %d %H:%M:%S %z %Y').timestamp()


def prior_context(row, indexed):
    context, seen = [], {row['tweet_id']}
    parent = row['in_response_to_tweet_id']
    child_time = timestamp(row)
    missing, cycle, time_error = False, False, False
    while parent:
        if parent in seen:
            cycle = True
            break
        seen.add(parent)
        ancestor = indexed.get(parent)
        if not ancestor:
            missing = True
            break
        ancestor_time = timestamp(ancestor)
        if ancestor_time > child_time:
            time_error = True
            break
        context.append({'tweet_id': parent, 'role': 'customer' if ancestor['inbound'].lower() == 'true' else 'support',
                        'text': ancestor['text'], 'created_at': ancestor['created_at']})
        child_time = ancestor_time
        parent = ancestor['in_response_to_tweet_id']
    context.reverse()
    return context, {'missing_parent': missing, 'cycle': cycle, 'timestamp_conflict': time_error}


def challenge_reason(row):
    text = row['text'].casefold()
    if re.search(r'hack|stolen|__email__|kill myself|suicid', text):
        return 'security_privacy_or_sensitive_terms'
    if len(normalized(text).split()) <= 3 and row['in_response_to_tweet_id']:
        return 'short_followup'
    if re.search(r'already|still|again|tried|twice|three times', text):
        return 'repeated_issue_terms'
    return None


def json_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    packet_path = args.repo/'annotations/batch-200.json'
    if packet_path.exists():
        raise SystemExit('Batch already exists. Refusing to replace a packet that may have human labels.')
    graph = Components()
    brand_ids = []
    total = 0
    print('Pass 1: reconstructing graph from both relationship columns...', flush=True)
    for row in rows(args.archive):
        total += 1
        i = int(row['tweet_id'])
        graph.ensure(i)
        links = row['response_tweet_id'].split(',') + [row['in_response_to_tweet_id']]
        for link in links:
            if link.strip():
                graph.union(i, int(link.strip()))
        if row['inbound'].lower() == 'false' and row['author_id'] == 'SpotifyCares':
            brand_ids.append(i)
    brand_components = {graph.find(i) for i in brand_ids}
    excluded = set()
    for file in (args.repo/'data/discovery').glob('*.json'):
        if file.name == 'profile.json':
            continue
        for pair in json.loads(file.read_text(encoding='utf-8')):
            for role in ('customer', 'support'):
                excluded.add(graph.find(int(pair[role]['tweet_id'])))
    print('Pass 2: retaining Spotify-connected rows...', flush=True)
    indexed = {}
    by_component = defaultdict(list)
    multi_brand = set()
    for row in rows(args.archive):
        component = graph.find(int(row['tweet_id']))
        if component not in brand_components:
            continue
        indexed[row['tweet_id']] = row
        by_component[component].append(row)
        if row['inbound'].lower() == 'false' and row['author_id'] != 'SpotifyCares':
            multi_brand.add(component)
    excluded |= multi_brand
    eligible_by_component = defaultdict(set)
    for row in indexed.values():
        if row['author_id'] != 'SpotifyCares' or row['inbound'].lower() != 'false':
            continue
        customer = indexed.get(row['in_response_to_tweet_id'])
        component = graph.find(int(row['tweet_id']))
        if customer and customer['inbound'].lower() == 'true' and component not in excluded:
            if normalized(customer['text']):
                eligible_by_component[component].add(customer['tweet_id'])
    # One uniformly selected eligible customer message per conversation, then shuffle conversations.
    rng = random.Random(20260910)
    candidates = []
    for component in sorted(eligible_by_component):
        tweet_id = rng.choice(sorted(eligible_by_component[component], key=int))
        candidates.append((component, indexed[tweet_id]))
    rng.shuffle(candidates)
    # Exploration texts are excluded by content similarity as well as graph membership.
    similarity = SimilarityIndex()
    for file in (args.repo/'data/discovery').glob('*.json'):
        if file.name != 'profile.json':
            for pair in json.loads(file.read_text(encoding='utf-8')):
                similarity.add(pair['customer']['text'])
    selected = []
    used = set()
    for component, row in candidates:
        if similarity.similar(row['text']):
            continue
        selected.append((component, row, 'dev' if len(selected) < 50 else 'test_representative', None))
        used.add(component)
        similarity.add(row['text'])
        if len(selected) == 170:
            break
    for component, row in candidates:
        reason = challenge_reason(row)
        if component in used or not reason or similarity.similar(row['text']):
            continue
        selected.append((component, row, 'test_challenge', reason))
        used.add(component)
        similarity.add(row['text'])
        if len(selected) == 200:
            break
    if len(selected) != 200:
        raise ValueError('Insufficient eligible examples')
    packet = []
    for component, row, split, reason in selected:
        context, context_status = prior_context(row, indexed)
        packet.append({'tweet_id': row['tweet_id'], 'component_id': str(component),
                       'split': split, 'challenge_selection_reason': reason,
                       'message': row['text'], 'created_at': row['created_at'],
                       'context': context, 'context_status': context_status})
    # Also remove retrieval components sharing a near-duplicate customer message with discovery/evaluation.
    retrieval_components = []
    scrubbed = 0
    for component in sorted(by_component):
        if component in excluded or component in used:
            continue
        if any(similarity.similar(r['text']) for r in by_component[component] if r['inbound'].lower() == 'true'):
            scrubbed += 1
            continue
        retrieval_components.append(component)
    rng.shuffle(retrieval_components)
    retrieval_components = set(retrieval_components[:3000])
    retrieval = []
    for component in sorted(retrieval_components):
        for row in by_component[component]:
            if row['author_id'] != 'SpotifyCares' or row['inbound'].lower() != 'false':
                continue
            customer = indexed.get(row['in_response_to_tweet_id'])
            if not customer or customer['inbound'].lower() != 'true' or timestamp(row) < timestamp(customer):
                continue
            retrieval.append({'component_id': str(component), 'customer_tweet_id': customer['tweet_id'],
                              'support_tweet_id': row['tweet_id'], 'customer_message': customer['text'],
                              'historical_reply': row['text'], 'created_at': row['created_at'],
                              'resolution_verified': False})
    # Leak checks on actual exports, not just requested split sizes.
    assert len({x['component_id'] for x in packet}) == 200
    assert not ({int(x['component_id']) for x in packet} & retrieval_components)
    assert not (used & excluded)
    assert all(x['tweet_id'] not in {c['tweet_id'] for c in x['context']} for x in packet)
    encoded = json.dumps(packet, sort_keys=True, ensure_ascii=False).encode('utf-8')
    packet_id = hashlib.sha256(encoded).hexdigest()
    json_write(packet_path, {'packet_id': packet_id, 'guide_version': '0.2', 'examples': packet})
    json_write(args.repo/'data/retrieval/history.json', retrieval)
    # Freeze expected IDs in a separate manifest; no future target answers are included.
    manifest = {'seed': 20260910, 'guide_version': '0.2', 'packet_id': packet_id,
                'total_archive_rows': total, 'spotify_connected_components': len(brand_components),
                'spotify_connected_rows': len(indexed), 'excluded_components': len(excluded & brand_components),
                'multi_brand_components': len(multi_brand), 'eligible_components': len(eligible_by_component),
                'split_counts': dict(Counter(x['split'] for x in packet)),
                'with_earlier_context': sum(bool(x['context']) for x in packet),
                'incomplete_context': sum(any(x['context_status'].values()) for x in packet),
                'retrieval_components_removed_for_text_overlap': scrubbed,
                'retrieval_components': len(retrieval_components), 'retrieval_pairs': len(retrieval),
                'challenge_counts': dict(Counter(x['challenge_selection_reason'] for x in packet if x['split']=='test_challenge')),
                'split_ids': {split: [x['tweet_id'] for x in packet if x['split']==split] for split in ['dev','test_representative','test_challenge']},
                'sampling_unit': 'One random directly answered customer message per eligible conversation component; shuffled components, with text-overlap exclusions. Challenge subset selected separately by predefined text heuristics.',
                'deduplication': 'Mentions/URLs removed, Unicode word normalization; exact matches for <4 tokens or word-trigram Jaccard >=0.8. This does not prove absence of semantic paraphrases.',
                'checks': {'unique_components': True, 'retrieval_component_disjoint': True, 'discovery_component_disjoint': True, 'no_target_in_context': True}}
    json_write(args.repo/'data/split-manifest.json', manifest)
    print(json.dumps({k:v for k,v in manifest.items() if k != 'split_ids'}, indent=2), flush=True)


if __name__ == '__main__':
    main()
