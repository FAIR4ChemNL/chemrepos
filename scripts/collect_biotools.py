"""Finds the entries of bio.tools (API documentation) for the repositories in
_data/repositories/. Run it with `make collect-biotools`; it takes about 45 minutes, and
continues where it stopped if it is interrupted.

All of bio.tools is downloaded (the answers of the API are cached as they are in
cache/documentation/bio.tools/) and searched here, so `--from-cache` redoes the matching
without downloading. The result is _data/documentation/bio.tools.json.

A repository matches an entry with the same website, or exactly the same name.
"""

import sys
import urllib.error
from datetime import date

from documentation_common import (ROOT, arguments, load, MIN_TERM, pages, same_resource,
                                  write)

BIOTOOLS = 'https://bio.tools'


def entries(from_cache, pause):
    url = lambda n: f'{BIOTOOLS}/api/t/?format=json&page={n}'  # noqa: E731
    for page in pages('bio.tools', url, lambda p: p.get('next'), from_cache, pause):
        yield from page['list']


def api_documentation(tool):
    return [d['url'] for d in tool.get('documentation') or []
            if d.get('url') and any('API' in t for t in d.get('type') or [])]


def match_biotools(repos, entries):
    """bio.tools entries for repositories: the same website, or exactly the same name.

    A name alone is weak: it counts only when it is written exactly the same (PRISM is
    not PriSM) and when no other tool has that name.
    """
    entries = list(entries)
    names = {}
    for repo in repos:
        for name in (repo['name'], repo['abbreviation']):
            if name and len(name.strip()) >= MIN_TERM:
                names.setdefault(name.strip(), []).append(repo)
    owners = {}
    for tool in entries:
        owners.setdefault(tool['name'].strip(), []).append(tool)
    found = {}
    for tool in entries:
        hits = {}
        for repo in repos:
            if same_resource(repo.get('homepage'), tool.get('homepage')):
                hits[repo['slug']] = 'homepage'
        if len(owners[tool['name'].strip()]) == 1:
            for repo in names.get(tool['name'].strip(), []):
                hits.setdefault(repo['slug'], 'name')
        for slug, how in hits.items():
            found.setdefault(slug, []).append({
                'id': tool['biotoolsID'], 'name': tool['name'],
                'url': f"{BIOTOOLS}/{tool['biotoolsID']}", 'homepage': tool.get('homepage'),
                'tool_types': tool.get('toolType') or [],
                'api_documentation': api_documentation(tool), 'matched_on': how})
    return found


def main():
    args = arguments(__doc__)
    repos = load()
    try:
        tools = list(entries(args.from_cache, args.pause))
    except urllib.error.URLError as error:
        sys.exit(f'Request failed: {error}')
    if not tools:
        sys.exit('cache/documentation/bio.tools is empty: run without --from-cache first.')
    result = {'source': 'bio.tools', 'url': BIOTOOLS, 'retrieved': date.today().isoformat(),
              'entries': len(tools), 'matches': match_biotools(repos, tools)}
    path = write('bio.tools', result)
    print(f'bio.tools: {len(result["matches"])} of {len(repos)} repositories have an entry '
          f'-> {path.relative_to(ROOT)}  ({len(tools)} entries)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
