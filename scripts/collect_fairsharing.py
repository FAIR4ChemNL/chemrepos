"""Collects chemistry data repositories from FAIRsharing into _data/repositories/.
Run it with `make collect`.

The FAIRsharing API needs an account: set FAIRSHARING_USER and FAIRSHARING_PASSWORD.
The raw answers are kept in cache/, so `--from-cache` redoes the processing without
logging in. API documentation: https://fairsharing.org/API_doc
(a copy is in background/FAIRsharing.mhtml).
"""

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / 'cache' / 'fairsharing-raw.json'
# Records the API does not give (yet), saved as pages from the website: <id>.html
PAGES = ROOT / 'cache' / 'fairsharing-pages'
OUTPUT = ROOT / '_data' / 'repositories' / 'fairsharing.json'
API = 'https://api.fairsharing.org'
PAGE_SIZE = 100
PAUSE = 1.0  # seconds between requests, to stay below the rate limit
WAITS = [30, 60, 120, 240]  # seconds to wait after a 429, one entry per retry

# FAIRsharing subjects; a search on `subjects` is an exact match, so one query each.
CHEMISTRY_SUBJECTS = [
    'Chemistry', 'Chemical Biology', 'Cheminformatics', 'Analytical Chemistry',
    'Organic Chemistry', 'Inorganic Chemistry', 'Physical Chemistry',
    'Computational Chemistry', 'Biochemistry', 'Spectroscopy', 'Crystallography',
    'Materials Science', 'Polymer Science', 'Metabolomics', 'Chemoinformatics',
]
# Repositories for any kind of data: relevant for chemistry data without a better home.
GENERAL_SUBJECTS = ['Subject Agnostic']
# FAIRsharing record types that accept deposits (the others are knowledgebases only).
REPOSITORY_TYPES = {'repository', 'knowledgebase_and_repository'}


def request(path, payload=None, token=None, method=None):
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = json.dumps(payload).encode() if payload is not None else None
    for attempt in range(len(WAITS) + 1):
        req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                answer = json.load(response)
            time.sleep(PAUSE)
            return answer
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == len(WAITS):
                raise
            wait = WAITS[attempt]
            print(f'429 Too Many Requests: waiting {wait} s '
                  f'(retry {attempt + 1}/{len(WAITS)})', file=sys.stderr)
            time.sleep(wait)


def login():
    user, password = os.environ.get('FAIRSHARING_USER'), os.environ.get('FAIRSHARING_PASSWORD')
    if not user or not password:
        sys.exit('Set FAIRSHARING_USER and FAIRSHARING_PASSWORD (a FAIRsharing account is '
                 'needed for the API), or use --from-cache.')
    answer = request('/users/sign_in', {'user': {'login': user, 'password': password}})
    return answer['jwt']


def search(token, subject):
    """Yields the raw records of one subject, all pages."""
    page = 1
    while True:
        query = urllib.parse.urlencode({
            'fairsharing_registry': 'database', 'subjects': subject,
            'page[number]': page, 'page[size]': PAGE_SIZE})
        answer = request('/search/fairsharing_records?' + query, token=token, method='POST')
        yield from answer.get('data', [])
        meta = answer.get('meta') or {}
        total = meta.get('total_pages')
        if not answer.get('data') or (total is not None and page >= int(total)):
            return
        if total is None and len(answer['data']) < PAGE_SIZE:
            return
        page += 1


def save_cache(raw, done):
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps({'records': raw, 'done': sorted(done)}, indent=1))


def fetch():
    token = login()
    # Resume after an interrupted run: subjects done are listed in the cache.
    saved = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    raw, done = saved.get('records', {}), set(saved.get('done', []))
    for scope, subjects in (('chemistry', CHEMISTRY_SUBJECTS), ('general', GENERAL_SUBJECTS)):
        for subject in subjects:
            if subject in done:
                continue
            found = 0
            for record in search(token, subject):
                entry = raw.setdefault(str(record['id']), {'record': record, 'queries': []})
                entry['queries'].append({'scope': scope, 'subject': subject})
                found += 1
            done.add(subject)
            save_cache(raw, done)
            print(f'{subject}: {found} records', file=sys.stderr)
    return raw


# --- processing -------------------------------------------------------------
# The shape of the records is read defensively: names are taken from the
# attributes, falling back to their `metadata`.

def names(value):
    """A list of FAIRsharing objects or strings as a list of their names."""
    result = []
    for item in value or []:
        if isinstance(item, dict):
            item = (item.get('name') or item.get('label') or item.get('licence_name')
                    or item.get('organisation_name') or '')
        if item:
            result.append(str(item).strip())
    return sorted(set(result))


def pick(attributes, *keys, metadata_first=False):
    """The first value among the keys. The top level of a record has generated
    texts ("FAIRsharing record for: ..."); the metadata has the original ones."""
    metadata = attributes.get('metadata') or {}
    sources = (metadata, attributes) if metadata_first else (attributes, metadata)
    for key in keys:
        for source in sources:
            if source.get(key) not in (None, '', []):
                return source[key]
    return None


def condition(value):
    """The access or deposition condition as given: {'type': ..., 'notes': ...}."""
    return value or None


def process(entry):
    record = entry['record']
    attributes = record.get('attributes', record)
    doi = pick(attributes, 'doi')
    subjects = names(pick(attributes, 'subjects'))
    domains = names(pick(attributes, 'domains'))
    countries = names(pick(attributes, 'countries'))
    licences = [
        {'id': l.get('licence_id'), 'name': l.get('licence_name'),
         'url': l.get('licence_url'), 'relation': l.get('relation')}
        for l in pick(attributes, 'licence_links') or [] if isinstance(l, dict)]
    organisations = [
        {'name': o.get('organisation_name'), 'types': o.get('organisation_types'),
         'relation': o.get('relation')}
        for o in attributes.get('organisation_links') or [] if isinstance(o, dict)]
    # Policies (of journals, publishers, funders) that recommend this repository.
    recommended_by = [
        {'name': link.get('linking_record_name'), 'type': link.get('linking_record_type'),
         'url': link.get('linking_record_url')}
        for link in attributes.get('linking_records') or []
        if link.get('linking_record_registry') == 'Policy' and link.get('relation') == 'recommends']
    name = pick(attributes, 'name', metadata_first=True)
    description = pick(attributes, 'description', metadata_first=True)
    item = {
        'id': str(record['id']),
        'name': name,
        'abbreviation': pick(attributes, 'abbreviation', metadata_first=True),
        'fairsharing_doi': doi,
        'fairsharing_url': f'https://doi.org/{doi}' if doi else
        f'https://fairsharing.org/{record["id"]}',
        'homepage': pick(attributes, 'homepage', metadata_first=True),
        'description': description,
        'record_type': pick(attributes, 'record_type', 'fairsharing_record_type'),
        'status': pick(attributes, 'status'),
        'subjects': subjects,
        'domains': domains,
        'taxonomies': names(pick(attributes, 'taxonomies')),
        'user_defined_tags': names(pick(attributes, 'user_defined_tags')),
        'object_types': names(pick(attributes, 'object_types')),
        'countries': countries,
        'licences': licences,
        'data_access': condition(pick(attributes, 'data_access_condition')),
        'data_deposition': condition(pick(attributes, 'data_deposition_condition')),
        'deprecated': bool(pick(attributes, 'deprecation_date')),
        'organisations': organisations,
        'recommended_by': recommended_by,
        'scope': 'chemistry' if any(q['scope'] == 'chemistry' for q in entry['queries'])
        else 'general',
        'matched_subjects': sorted({q['subject'] for q in entry['queries']}),
    }
    return item


def text_of(fragment):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', fragment))).strip()


def process_page(path):
    """A record from a saved page of the website, for a record that is not (yet) public.

    Only what the page shows: what it does not show is None or empty.
    """
    page = path.read_text(encoding='utf-8')
    page = re.sub(r'<!--.*?-->', '', page, flags=re.S)
    # The page lists "<b>Label</b>" followed by the value, until the next label.
    parts = re.split(r'<span[^>]*><i[^>]*></i><b[^>]*>([^<]*)</b></span>', page)
    fields = {parts[i].strip(): parts[i + 1] for i in range(1, len(parts) - 1, 2)}

    def chips(label):
        return sorted(set(text_of(c) for c in re.findall(
            r'<div class="v-chip__content"[^>]*><div[^>]*><div[^>]*>([^<]+)</div>',
            fields.get(label, ''))))

    def one(label):
        value = text_of(fields.get(label, ''))
        return None if value in ('', 'None found') else value
    head = re.search(r'<h3[^>]*>([^<]*)</h3><b[^>]*>([^<]*)</b>', page)
    organisations = [
        {'name': text_of(name), 'types': [kind.strip(' ()')], 'relation': 'maintains'}
        for name, kind in re.findall(
            r'Organisations maintaining this resource.*?<a href="https://fairsharing.org/organisations/\d+"[^>]*>(.*?)</a>.*?<p[^>]*>(.*?)</p>',
            page, flags=re.S) for name, kind in [(name, text_of(kind))]]
    subjects = chips('Subjects')
    return {
        'id': path.stem,
        'name': head.group(1).strip(),
        'abbreviation': head.group(2).strip(' ()'),
        'fairsharing_doi': None,
        'fairsharing_url': f'https://fairsharing.org/{path.stem}',
        'homepage': one('Homepage'),
        'description': one('Description'),
        'record_type': (one('Type') or '').lower() or None,
        'status': 'hidden',
        'subjects': subjects,
        'domains': chips('Domains'),
        'taxonomies': chips('Taxonomic Range'),
        'user_defined_tags': chips('User Defined Tags'),
        'object_types': chips('Object types in scope for this resource'),
        'countries': [text_of(c) for c in re.findall(r'<p[^>]*>([^<]*)</p></a>', fields.get('Countries developing this resource', ''))],
        'licences': [],
        'data_access': None,
        'data_deposition': None,
        'deprecated': False,
        'organisations': organisations,
        'recommended_by': [],
        'scope': 'chemistry' if set(subjects) & set(CHEMISTRY_SUBJECTS) else 'general',
        'matched_subjects': sorted(set(subjects) & set(CHEMISTRY_SUBJECTS + GENERAL_SUBJECTS)),
        'from_page': True,
    }


def is_repository(item):
    kind = str(item['record_type'] or '').lower().replace(' ', '_').replace('/', '_and_')
    # An unknown type is kept: better to show it than to lose a repository.
    return not kind or kind in REPOSITORY_TYPES or 'repository' in kind


def coverage(items):
    """How many records give a value for what the decision tree asks."""
    def count(f):
        return sum(1 for i in items if f(i))
    return {
        'records': len(items),
        'subjects (discipline)': count(lambda i: i['subjects']),
        'licences (license)': count(lambda i: i['licences']),
        'countries (region, country)': count(lambda i: i['countries']),
        'data_access (sensitivity, restricted-access)': count(lambda i: i['data_access']),
        'data_deposition': count(lambda i: i['data_deposition']),
        'recommended_by (journal-requirement, funder-requirement)':
            count(lambda i: i['recommended_by']),
        'organisations (institutional-repository)': count(lambda i: i['organisations']),
        'persistent-identifier, size, cost': 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--fresh', action='store_true',
                        help='ignore the cache and query every subject again')
    parser.add_argument('--from-cache', action='store_true',
                        help='process cache/fairsharing-raw.json instead of calling the API')
    args = parser.parse_args()
    if args.fresh and not args.from_cache:
        CACHE.unlink(missing_ok=True)
    try:
        raw = json.loads(CACHE.read_text())['records'] if args.from_cache else fetch()
    except FileNotFoundError:
        sys.exit(f'{CACHE} does not exist: run without --from-cache first.')
    except urllib.error.URLError as error:
        sys.exit(f'FAIRsharing request failed: {error}')
    items = [i for i in map(process, raw.values()) if is_repository(i) and not i['deprecated']]
    # Records that are not public yet, saved from their page; the API wins once it has them.
    known = {i['id'] for i in items}
    items += [i for i in map(process_page, sorted(PAGES.glob('*.html')))
              if i['id'] not in known and is_repository(i)]
    items.sort(key=lambda i: (i['name'] or '').lower())
    result = {
        'source': 'FAIRsharing', 'url': 'https://fairsharing.org',
        'licence': 'CC BY-SA 4.0', 'retrieved': date.today().isoformat(),
        'queries': {'subjects': CHEMISTRY_SUBJECTS, 'general_subjects': GENERAL_SUBJECTS},
        'coverage': coverage(items), 'items': items,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(f'{len(items)} repositories ({Counter(i["scope"] for i in items).most_common()}) '
          f'-> {OUTPUT.relative_to(ROOT)}')
    for key, value in result['coverage'].items():
        print(f'  {value:5}  {key}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
