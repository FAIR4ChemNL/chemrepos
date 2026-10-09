"""Collects chemistry data repositories from FAIRsharing into _data/repositories/.
Run it with `make collect`.

The FAIRsharing API needs an account: set FAIRSHARING_USER and FAIRSHARING_PASSWORD.
The raw answers are kept in cache/, so `--from-cache` redoes the processing without
logging in. API documentation: https://fairsharing.org/API_doc
(a copy is in background/FAIRsharing.mhtml).
"""

import argparse
import json
import os
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

# What a data-type answer (questions/data-type.json) means in FAIRsharing terms:
# words that occur in the subjects, domains, name or description of a record.
DATA_TYPE_WORDS = {
    'spectra': ['spectr', 'nmr', 'mass spec', 'infrared'],
    'crystal-structures': ['crystal', 'diffraction'],
    'computational': ['computational chem', 'quantum', 'molecular dynamics', 'simulation'],
    'compounds': ['compound', 'chemical structure', 'reaction', 'small molecule',
                  'cheminformatics', 'chemoinformatics'],
    'assays': ['assay', 'bioactivity', 'chemical biology', 'screening'],
    'materials': ['material', 'polymer'],
    'images': ['image', 'imaging', 'microscop'],
}
EU = {
    'austria', 'belgium', 'bulgaria', 'croatia', 'cyprus', 'czechia', 'czech republic',
    'denmark', 'estonia', 'finland', 'france', 'germany', 'greece', 'hungary', 'ireland',
    'italy', 'latvia', 'lithuania', 'luxembourg', 'malta', 'netherlands', 'poland',
    'portugal', 'romania', 'slovakia', 'slovenia', 'spain', 'sweden',
}


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


def licence_class(name):
    n = name.lower()
    if 'cc0' in n or 'public domain' in n or 'zero' in n:
        return 'cc0'
    if ('cc by' in n or 'creative commons attribution' in n) and not any(
            w in n for w in ('-nc', ' nc', 'noncommercial', 'non-commercial', '-nd', ' nd')):
        return 'cc-by' if '-sa' not in n and ' sa' not in n else 'other-open'
    if 'public domain' in n or 'pddl' in n:
        return 'cc0'
    if any(w in n for w in ('creative commons', 'open data commons', 'odbl', 'apache',
                            'gpl', 'bsd', 'mit license', 'open government', 'open licen')):
        return 'other-open'
    return 'other'


def condition(value):
    """{'type': 'open', 'notes': ...} as the type: open, partially open, controlled, ..."""
    kind = (value or {}).get('type')
    return None if kind in (None, 'not found', 'not applicable') else kind


def process(entry):
    record = entry['record']
    attributes = record.get('attributes', record)
    doi = pick(attributes, 'doi')
    subjects = names(pick(attributes, 'subjects'))
    domains = names(pick(attributes, 'domains'))
    countries = names(pick(attributes, 'countries'))
    licences = names(pick(attributes, 'licence_links'))
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
    text = ' '.join([name or '', description or '',
                     *subjects, *domains]).lower()
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
    # Values for the answers of the decision tree, keyed by `answer_key`.
    item['answers'] = {
        'data_type': [t for t, words in DATA_TYPE_WORDS.items()
                      if any(w in text for w in words)],
        'license': sorted({licence_class(l) for l in licences}),
        'country': [c.lower() for c in countries],
        'region_eu': bool(countries) and all(c.lower() in EU for c in countries),
    }
    return item


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
        'data_type (data-type, discipline)': count(lambda i: i['answers']['data_type']),
        'subjects (discipline)': count(lambda i: i['subjects']),
        'license (license)': count(lambda i: i['licences']),
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
    items = sorted((i for i in map(process, raw.values())
                    if is_repository(i) and not i['deprecated']),
                   key=lambda i: (i['name'] or '').lower())
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
