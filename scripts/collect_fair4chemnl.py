"""Finds the training materials of FAIR4ChemNL for the repositories in _data/repositories/.
Run it with `make collect-fair4chemnl`.

The materials are the Markdown files in the materials/ folder of
https://github.com/FAIR4ChemNL/training-material, read through GitHub's raw access and
cached as they are in cache/documentation/FAIR4ChemNL/ (so `--from-cache` redoes the
matching without downloading). The YAML at the top of each file describes the material
(name, url, keywords, description). The result is _data/documentation/fair4chemnl.json.

A repository matches a material that is about its website (the url of the material is
the homepage of the repository, or a page of it), or that has the name or abbreviation
of the repository, exactly as written, in its name, keywords or description. A name that
is an ordinary word is not searched.
"""

import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date

import yaml

from documentation_common import (CACHE, ROOT, arguments, load, lower_case_words, same_resource,
                                  terms, write)
from app.repositories import SHARED_HOSTS, address

REPOSITORY = 'FAIR4ChemNL/training-material'
RAW = f'https://raw.githubusercontent.com/{REPOSITORY}/main/materials/'
BLOB = f'https://github.com/{REPOSITORY}/blob/main/materials/'
FOLDER = CACHE / 'FAIR4ChemNL'


def get(name, from_cache, pause):
    """A file of the materials/ folder as the repository has it: from the cache, or downloaded."""
    path = FOLDER / name
    if from_cache or path.exists():
        return path.read_text(encoding='utf-8')
    request = urllib.request.Request(RAW + name, headers={
        'User-Agent': 'chemrepos (research data repository finder)'})
    with urllib.request.urlopen(request, timeout=60) as response:
        text = response.read().decode('utf-8')
    FOLDER.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    time.sleep(pause)
    return text


def metadata(text):
    """The `trainingMaterial` of the YAML at the top of a file (between the two ---)."""
    header = text.split('---')[1]
    return yaml.safe_load(header)['trainingMaterial']


def materials(from_cache, pause):
    index = get('index.md', from_cache, pause)  # the generated list of all materials
    for name in re.findall(r'\]\((\d+\.md)\)', index):
        yield name, metadata(get(name, from_cache, pause))


def keywords_of(material):
    value = material.get('keywords') or ''
    return [k.strip() for k in (value.split(',') if isinstance(value, str) else value)]


def below(homepage, url):
    """Whether a url is a page of the website of a repository."""
    home, page = address(homepage), address(url)
    return bool(home) and home.partition('/')[0] not in SHARED_HOSTS and page.startswith(home + '/')


def match(repos, found, words):
    searches = {r['slug']: terms(r, words) for r in repos}
    result = {}
    for name, material in found:
        urls = [material.get('url'), material.get('@id')]
        blob = ' \n '.join([material.get('name') or '', *keywords_of(material),
                            material.get('description') or ''])
        for repo in repos:
            how = None
            if any(same_resource(repo.get('homepage'), u) or below(repo.get('homepage'), u)
                   for u in urls if u):
                how = 'website'
            elif any(t in blob and rx.search(blob) for t, rx in searches[repo['slug']].items()):
                how = 'text'
            if how:
                result.setdefault(repo['slug'], {}).setdefault('materials', []).append({
                    'id': name.removesuffix('.md'), 'title': material.get('name'),
                    'url': material.get('url') or BLOB + name, 'source_file': BLOB + name,
                    'keywords': keywords_of(material), 'start': None, 'matched_on': how})
    return result


def main():
    args = arguments(__doc__)
    repos = load()
    try:
        found = list(materials(args.from_cache, args.pause))
    except (urllib.error.URLError, FileNotFoundError) as error:
        sys.exit(f'Could not read the materials: {error}. Run without --from-cache first.')
    result = {'source': 'FAIR4ChemNL', 'url': f'https://github.com/{REPOSITORY}',
              'retrieved': date.today().isoformat(), 'entries': {'materials': len(found)},
              'matches': match(repos, found, lower_case_words())}
    path = write('fair4chemnl', result)
    print(f'FAIR4ChemNL: {len(result["matches"])} of {len(repos)} repositories have a material '
          f'-> {path.relative_to(ROOT)}  ({len(found)} materials)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
