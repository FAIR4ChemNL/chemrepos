"""Collects the services of NFDI4Cat from https://nfdi4cat.org/nfdi4cat/en/Services.html
into _data/services/nfdi4cat.json. Run it with `make collect-nfdi4cat`.

The pages are cached as they are in cache/nfdi4cat/, so `--from-cache` redoes the
processing without downloading.
"""

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / 'cache' / 'nfdi4cat'
OUTPUT = ROOT / '_data' / 'services' / 'nfdi4cat.json'
SERVICES = 'https://nfdi4cat.org/nfdi4cat/en/Services.html'
PAUSE = 1.0  # seconds between requests


def download(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'chemrepos (research data repository finder)'})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
    time.sleep(PAUSE)
    return body.decode('utf-8')


def cached(name, url, from_cache):
    """The page as the website gave it: cached verbatim, downloaded if needed."""
    path = CACHE / name
    if from_cache:
        return path.read_text(encoding='utf-8')
    text = download(url)
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return text


def text_of(fragment):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', fragment))).strip()


def main_of(page):
    start, end = page.find('<main'), page.find('</main>')
    return re.sub(r'<(script|style)[^>]*>.*?</\1>', '', page[start:end], flags=re.S)


def cards(overview):
    """The service cards of the overview: link, text, personas, development status."""
    found = []
    for personas, body in re.findall(
            r'<div class="col service-item" data-personas="([^"]*)">(.*?)</a>\s*</div>',
            main_of(overview), flags=re.S):
        found.append({
            'href': re.search(r'href="([^"]+)"', body).group(1),
            'description': text_of(re.search(r'<p class="card-text">(.*?)</p>', body, re.S).group(1)),
            'personas': personas.split(),
            'in_development': 'dev-ribbon' in body,
        })
    return found


def service(card, page):
    main = main_of(page)
    caption = re.search(r'<p class="service-headline-caption[^"]*">(.*?)</p>', main, re.S)
    # The text of the page after the buttons: short description, problem statement, ...
    body = main[main.find('<div class="container mb-4">'):]
    links = []  # the page repeats its buttons for small screens: identical links once
    for u, t in re.findall(r'<a [^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', body, flags=re.S):
        link = {'text': text_of(t), 'url': u}
        if link not in links:
            links.append(link)
    url = urljoin(SERVICES, card['href'])
    return {
        'id': url.rsplit('/', 1)[-1].removesuffix('.html'),
        'name': text_of(re.search(r'<h1[^>]*>(.*?)</h1>', main, re.S).group(1)),
        'url': url,
        'description': card['description'],
        'authors': text_of(caption.group(1)) if caption else None,
        'personas': card['personas'],
        'in_development': card['in_development'],
        'links': links,
        'text': text_of(body),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--from-cache', action='store_true',
                        help='process cache/nfdi4cat/ instead of downloading')
    args = parser.parse_args()
    try:
        overview = cached('Services.html', SERVICES, args.from_cache)
        items = []
        for card in cards(overview):
            url = urljoin(SERVICES, card['href'])
            name = url.rsplit('/', 1)[-1]
            items.append(service(card, cached(name, url, args.from_cache)))
    except FileNotFoundError as error:
        sys.exit(f'{error.filename} does not exist: run without --from-cache first.')
    except urllib.error.URLError as error:
        sys.exit(f'Request failed: {error}')
    result = {'source': 'NFDI4Cat', 'url': SERVICES, 'retrieved': date.today().isoformat(),
              'items': items}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(f'{len(items)} services -> {OUTPUT.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
