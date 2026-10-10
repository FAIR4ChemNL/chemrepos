"""Collects the services of NFDI4Chem from https://nfdi4chem.de/support/
into _data/services/nfdi4chem.json. Run it with `make collect-nfdi4chem`.

The page is cached as it is in cache/nfdi4chem/, so `--from-cache` redoes the
processing without downloading. Only that page is downloaded: the services
themselves are on other websites.
"""

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / 'cache' / 'nfdi4chem' / 'support.html'
OUTPUT = ROOT / '_data' / 'services' / 'nfdi4chem.json'
PAGE = 'https://nfdi4chem.de/support/'


def get_page(from_cache):
    """The page as the website gave it: cached verbatim, downloaded if needed."""
    if from_cache:
        return CACHE.read_text(encoding='utf-8')
    request = urllib.request.Request(PAGE, headers={
        'User-Agent': 'chemrepos (research data repository finder)'})
    with urllib.request.urlopen(request, timeout=60) as response:
        text = response.read().decode('utf-8')
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(text, encoding='utf-8')
    return text


def text_of(fragment):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', fragment))).strip()


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def services(page):
    """The links of the page, with the step ("1. Plan your research data") they are listed under."""
    start, end = page.find('<main'), page.find('</main>')
    main = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', page[start:end], flags=re.S)
    tokens = re.finditer(
        r'<h3[^>]*>(?P<h3>\d\.[^<]*)</h3>(?:\s*<[^>]*>)*?\s*<p[^>]*><em>(?P<h3sub>.*?)</em>'
        r'|<strong>(?P<step>\d\.[^<]*)</strong><br\s*/?><em>(?P<sub>.*?)</em>'
        r'|<li><a href="(?P<url>[^"]+)">(?P<name>.*?)</a></li>', main, flags=re.S)
    found, step, description = [], None, None
    for token in tokens:
        if token.group('h3') or token.group('step'):
            step = text_of(token.group('h3') or token.group('step'))
            description = text_of(token.group('h3sub') or token.group('sub'))
        elif step:
            name = text_of(token.group('name'))
            found.append({
                'id': slug(name),
                'name': name,
                'url': token.group('url'),
                'links': [{'text': name, 'url': token.group('url')}],
                'step': step,
                'step_description': description,
                # "Learn more about ... in our knowledge base" are pages about a step, not services.
                'documentation': name.startswith('Learn more'),
            })
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--from-cache', action='store_true',
                        help='process cache/nfdi4chem/ instead of downloading')
    args = parser.parse_args()
    try:
        items = services(get_page(args.from_cache))
    except FileNotFoundError as error:
        sys.exit(f'{error.filename} does not exist: run without --from-cache first.')
    except urllib.error.URLError as error:
        sys.exit(f'Request failed: {error}')
    result = {'source': 'NFDI4Chem', 'url': PAGE, 'retrieved': date.today().isoformat(),
              'items': items}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(f'{len(items)} links ({sum(not i["documentation"] for i in items)} services) '
          f'-> {OUTPUT.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
