"""Download the original public Kaggle archive (Python standard library only)."""
import argparse
from pathlib import Path
import urllib.request
import zipfile

URL = 'https://www.kaggle.com/api/v1/datasets/download/thoughtvector/customer-support-on-twitter'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=Path('data/raw/twitter.zip'))
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        raise SystemExit(f'{args.out} already exists; choose another path to download again.')
    temporary = args.out.with_suffix('.zip.part')
    request = urllib.request.Request(URL, headers={'User-Agent': 'hiver-assignment-data-preparation/0.1'})
    with urllib.request.urlopen(request, timeout=60) as source, temporary.open('wb') as dest:
        while chunk := source.read(1024 * 1024):
            dest.write(chunk)
    if not zipfile.is_zipfile(temporary):
        raise SystemExit(f'Response was not a ZIP. Inspect {temporary}; Kaggle may require manual download.')
    temporary.rename(args.out)
    print(args.out)

if __name__ == '__main__':
    main()
