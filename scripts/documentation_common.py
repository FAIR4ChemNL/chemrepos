"""What the three collect scripts for documentation (collect_biotools.py,
collect_tess.py and collect_taxila.py) share: downloading, caching and matching.

The answers of the catalogues are cached as they are in cache/documentation/, and
each script writes its result to its own file in _data/documentation/.
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.repositories import load, same_resource, slugify  # noqa: E402,F401

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / 'cache' / 'documentation'
OUTPUT = ROOT / '_data' / 'documentation'
TESS_LIKE = {'TeSS': 'https://tess.elixir-europe.org', 'Taxila': 'https://taxila.nl'}
KINDS = ('materials', 'events')
PAGE_SIZE = 100
MIN_TERM = 4  # shorter names and abbreviations match too much by accident
ORDINARY = 25  # a word that is written in lower case this often in the entries is not a name


def arguments(description):
    parser = argparse.ArgumentParser(description=description.split('\n')[0])
    parser.add_argument('--from-cache', action='store_true',
                        help='use only what is in cache/documentation/')
    parser.add_argument('--pause', type=float, default=1.0,
                        help='seconds between requests (default 1)')
    return parser.parse_args()


def download(url, path, pause):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'chemrepos (research data repository finder)'})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                text = response.read().decode('utf-8')
            break
        except urllib.error.HTTPError as error:
            if error.code not in (429, 502, 503, 504) or attempt == 4:
                raise
            wait = 30 * 2 ** attempt
            print(f'HTTP {error.code}: waiting {wait} s', file=sys.stderr)
            time.sleep(wait)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    time.sleep(pause)
    return text


def pages(name, url_of, next_of, from_cache, pause):
    """The raw pages of a catalogue, one by one: from the cache, or downloaded and cached."""
    number = 1
    while True:
        path = CACHE / name / f'{number:04d}.json'
        if path.exists():
            text = path.read_text(encoding='utf-8')
        elif from_cache:
            return
        else:
            text = download(url_of(number), path, pause)
            if number % 10 == 0:
                print(f'{name}: page {number}', file=sys.stderr)
        page = json.loads(text)
        yield page
        if not next_of(page):
            return
        number += 1


def write(name, result):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / f'{name}.json'
    path.write_text(json.dumps(result, indent=1, ensure_ascii=False) + '\n')
    return path


# --- TeSS and Taxila ----------------------------------------------------------------

def tess_entries(source, kind, from_cache, pause):
    host = TESS_LIKE[source]
    url = lambda n: (f'{host}/{kind}.json_api?page_size={PAGE_SIZE}&page_number={n}'  # noqa: E731
                     '&include_expired=true')
    for page in pages(f'{source}/{kind}', url, lambda p: (p.get('links') or {}).get('next'),
                      from_cache, pause):
        for entry in page['data']:
            yield entry, host


def lower_case_words():
    """How often each word is written in lower case in the titles and descriptions of the
    cached entries of TeSS and Taxila together."""
    counts = Counter()
    for source in TESS_LIKE:
        for kind in KINDS:
            for path in sorted((CACHE / source / kind).glob('*.json')):
                for entry in json.loads(path.read_text(encoding='utf-8'))['data']:
                    a = entry['attributes']
                    counts.update(re.findall(
                        r'\b[a-z]{3,}\b', f"{a.get('title') or ''} {a.get('description') or ''}"))
    return counts


def terms(repo, words):
    """The names a repository is known by, that are long enough to search for.

    They are searched exactly as written (CORE is not core), and a single word that is
    also an ordinary word (Discovery, Core, Discover) is not searched for.
    """
    found = {}
    for name in (repo['name'], repo['abbreviation']):
        name = (name or '').strip()
        if len(name) < MIN_TERM or (' ' not in name and words[name.lower()] >= ORDINARY):
            continue
        found[name] = re.compile(r'(?<!\w)' + re.escape(name) + r'(?!\w)')
    return found


def biotools_matches():
    """The bio.tools entries found for the repositories by collect_biotools.py."""
    path = OUTPUT / 'bio.tools.json'
    return json.loads(path.read_text(encoding='utf-8'))['matches'] if path.exists() else {}


def match_tess(repos, entries, tools, words=None):
    """Entries of TeSS or Taxila that are about a repository."""
    entries = list(entries)
    words = words if words is not None else Counter()
    searches = {r['slug']: terms(r, words) for r in repos}
    tool_ids = {slug: {f"https://bio.tools/tool/{t['id']}" for t in tools.get(slug, [])}
                for slug in searches}
    found = {}
    for entry, host in entries:
        a = entry['attributes']
        resources = a.get('external-resources') or []
        linked = {(r.get('url') or '').rstrip('/') for r in resources}
        keywords = a.get('keywords') or []
        blob = ' \n '.join([a.get('title') or '', a.get('subtitle') or '',
                            *([keywords] if isinstance(keywords, str) else keywords),
                            *[r.get('title') or '' for r in resources]])
        for slug, wanted in searches.items():
            how = None
            if tool_ids[slug] & linked:
                how = 'link'
            elif any(t in blob and rx.search(blob) for t, rx in wanted.items()):
                how = 'text'
            if how:
                found.setdefault(slug, []).append({
                    'id': entry['id'], 'title': a.get('title'),
                    'url': host + entry['links']['self'], 'start': a.get('start'),
                    'matched_on': how})
    return found


def run_tess_like(source, description):
    """The whole of collect_tess.py and collect_taxila.py."""
    args = arguments(description)
    repos = load()
    try:
        loaded = {kind: list(tess_entries(source, kind, args.from_cache, args.pause))
                  for kind in KINDS}
    except urllib.error.URLError as error:
        sys.exit(f'Request failed: {error}')
    if not any(loaded.values()):
        sys.exit(f'{CACHE / source} is empty: run without --from-cache first.')
    words, tools = lower_case_words(), biotools_matches()
    result = {'source': source, 'url': TESS_LIKE[source], 'retrieved': date.today().isoformat(),
              'entries': {kind: len(loaded[kind]) for kind in KINDS}, 'matches': {}}
    for kind in KINDS:
        for slug, hits in match_tess(repos, loaded[kind], tools, words).items():
            hits.sort(key=lambda h: h['start'] or '', reverse=True)
            result['matches'].setdefault(slug, {})[kind] = hits
    path = write(source.lower(), result)
    print(f'{source}: {len(result["matches"])} of {len(repos)} repositories have materials '
          f'or events -> {path.relative_to(ROOT)}  {result["entries"]}')
    if not tools:
        print('  (no bio.tools matches yet: run collect_biotools.py first for the links '
              'to bio.tools entries)')
