"""Collects the ELIXIR Data Platform services from the bio.tools registry into
_data/services/elixir.json. Run it with `make collect-elixir`.

The website elixir-europe.org lists the services of ELIXIR but blocks scripts, so
this uses the registry of ELIXIR itself, https://bio.tools: the entries that are
marked as part of the ELIXIR Data Platform. The answers of the API are cached as they
are in cache/elixir/, so `--from-cache` redoes the processing without downloading.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / 'cache' / 'elixir'
OUTPUT = ROOT / '_data' / 'services' / 'elixir.json'
API = 'https://bio.tools/api/t/?format=json&elixirPlatform=Data&page={}'
PAUSE = 1.0  # seconds between requests


def get_pages(from_cache):
    """The raw answers of the API, one per page: cached verbatim, downloaded if needed."""
    pages, number = [], 1
    while True:
        path = CACHE / f'page-{number}.json'
        if from_cache:
            if not path.exists():
                break
            text = path.read_text(encoding='utf-8')
        else:
            request = urllib.request.Request(API.format(number), headers={
                'User-Agent': 'chemrepos (research data repository finder)'})
            with urllib.request.urlopen(request, timeout=60) as response:
                text = response.read().decode('utf-8')
            CACHE.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
            time.sleep(PAUSE)
        pages.append(json.loads(text))
        if not pages[-1].get('next'):
            break
        number += 1
    return pages


def service(tool):
    links = [{'text': 'Homepage', 'url': tool['homepage']}] if tool.get('homepage') else []
    links += [{'text': link.get('note') or 'Link', 'url': link['url']}
              for link in tool.get('link') or [] if link.get('url')]
    return {
        'id': tool['biotoolsID'],
        'name': tool['name'],
        'url': f"https://bio.tools/{tool['biotoolsID']}",
        'description': tool.get('description'),
        'links': links,
        'tool_types': tool.get('toolType') or [],
        'topics': [t['term'] for t in tool.get('topic') or []],
        'elixir_platforms': tool.get('elixirPlatform') or [],
        'elixir_nodes': tool.get('elixirNode') or [],
        'elixir_communities': tool.get('elixirCommunity') or [],
        'elixir_badge': bool(tool.get('elixir_badge')),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--from-cache', action='store_true',
                        help='process cache/elixir/ instead of downloading')
    args = parser.parse_args()
    try:
        pages = get_pages(args.from_cache)
    except urllib.error.URLError as error:
        sys.exit(f'Request failed: {error}')
    if not pages:
        sys.exit(f'{CACHE} is empty: run without --from-cache first.')
    items = [service(tool) for page in pages for tool in page['list']]
    result = {'source': 'ELIXIR', 'url': 'https://elixir-europe.org/services',
              'collected_from': 'https://bio.tools, entries with elixirPlatform=Data',
              'retrieved': date.today().isoformat(), 'items': items}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(f'{len(items)} services of {pages[0]["count"]} -> {OUTPUT.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
