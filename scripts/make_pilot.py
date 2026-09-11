"""Make a blank human worksheet from explicitly selected discovery examples."""
import json
from pathlib import Path

IDS = ('1500094', '602845', '1909997', '2728389', '2313472', '2251335',
       '57576', '2076929', '832174', '1726752', '2267527', '2121321')

def main():
    root = Path(__file__).resolve().parents[1]
    source = root / 'data/discovery/SpotifyCares.json'
    pairs = json.loads(source.read_text(encoding='utf-8'))
    indexed = {r['customer']['tweet_id']: r['customer'] for r in pairs}
    out = root / 'annotations/pilot.md'
    if out.exists():
        raise SystemExit('Pilot exists; refusing to overwrite possible human labels.')
    lines = ['# Human annotation pilot — 12 examples', '',
             'Purposefully selected to test guideline boundaries, not randomly sampled for scoring.',
             'Read docs/annotation-guide.md first. Earlier context is unavailable in this pilot.',
             'Do not consult historical responses. All label fields are intentionally blank.', '',
             'Annotator: ', 'Date: ', 'Guide version: 0.1', '']
    for i, tweet_id in enumerate(IDS, 1):
        r = indexed[tweet_id]
        lines += [f'## {i}. Tweet {tweet_id}', '',
                  'Earlier reply exists in source: ' + ('yes (not supplied)' if r['in_response_to_tweet_id'] else 'no recorded parent'), '',
                  *['> ' + line for line in r['text'].splitlines()], '',
                  '- Intent: ', '- Route (auto_handle / escalate): ', '- Reason code: ',
                  '- Rationale: ', '- Reply must include: ', '- Reply must avoid: ',
                  '- Ambiguous (yes / no), and why: ', '']
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines), encoding='utf-8')
    print(out)

if __name__ == '__main__':
    main()
