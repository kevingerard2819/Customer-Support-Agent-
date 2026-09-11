"""Profile the original Kaggle archive; sample real linked exchanges deterministically."""
import argparse
import collections
import csv
import hashlib
import io
import json
from pathlib import Path
import random
import zipfile

BRANDS = ('SpotifyCares', 'XboxSupport', 'AppleSupport', 'AmazonHelp')

def rows(archive):
    with zipfile.ZipFile(archive) as z:
        candidates = [n for n in z.namelist() if n.endswith('twcs.csv')]
        if len(candidates) != 1:
            raise ValueError(f'Expected one twcs.csv: {z.namelist()}')
        with z.open(candidates[0]) as f:
            yield from csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig'))

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    counts = collections.Counter()
    eligible = collections.Counter()
    samples = {b: [] for b in BRANDS}
    rng = {b: random.Random(42) for b in BRANDS}
    total = 0
    for row in rows(args.archive):
        total += 1
        if row['inbound'].lower() != 'false':
            continue
        brand = row['author_id']
        counts[brand] += 1
        if brand not in samples or not row['in_response_to_tweet_id']:
            continue
        eligible[brand] += 1
        sample = samples[brand]
        if len(sample) < 120:
            sample.append(row)
        else:
            i = rng[brand].randrange(eligible[brand])
            if i < 120:
                sample[i] = row
    wanted = {r['in_response_to_tweet_id'] for s in samples.values() for r in s}
    parents = {r['tweet_id']: r for r in rows(args.archive) if r['tweet_id'] in wanted}
    paired = {}
    for brand, sample in samples.items():
        pairs = [{'customer': parents[r['in_response_to_tweet_id']], 'support': r}
                 for r in sample if r['in_response_to_tweet_id'] in parents
                 and parents[r['in_response_to_tweet_id']]['inbound'].lower() == 'true']
        paired[brand] = len(pairs)
        (args.out / f'{brand}.json').write_text(json.dumps(pairs, indent=2, ensure_ascii=False), encoding='utf-8')
    with args.archive.open('rb') as f:
        sha = hashlib.file_digest(f, 'sha256').hexdigest()
    profile = {'source': 'https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter',
               'archive_sha256': sha, 'total_rows': total, 'support_tweets_by_brand': dict(counts.most_common()),
               'eligible_support_replies': dict(eligible), 'sample_size': 120, 'seed': 42,
               'valid_customer_support_pairs_in_sample': paired,
               'sampling_unit': 'support tweet with parent; NOT independent conversation or random customer message'}
    (args.out / 'profile.json').write_text(json.dumps(profile, indent=2), encoding='utf-8')
    print(json.dumps(profile, indent=2))

if __name__ == '__main__':
    main()
