"""The repositories in _data/repositories/ and what they say about the questions.

The repositories are used as they are collected (see scripts/). For each question
of the decision tree `facts()` tells which answers a repository supports (`yes`),
which it rules out (`no`), and shows the values of the repository itself (`info`).
Everything else is unknown. Nothing is changed in the repositories, and the
facts are derived from them on the fly.
"""

import json
import re

from .tree import ROOT

REPOSITORIES = ROOT / '_data' / 'repositories'

# Words in the subjects, name or description that suggest a type of data.
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
    'austria', 'belgium', 'bulgaria', 'croatia', 'cyprus', 'czech republic', 'czechia',
    'denmark', 'estonia', 'finland', 'france', 'germany', 'greece', 'hungary', 'ireland',
    'italy', 'latvia', 'lithuania', 'luxembourg', 'malta', 'netherlands', 'poland',
    'portugal', 'romania', 'slovakia', 'slovenia', 'spain', 'sweden',
}
# Places that say nothing about a country.
NOT_A_COUNTRY = {'worldwide', 'european union'}


def load(directory=REPOSITORIES):
    """All repositories of all sources, each with a `slug` and its `source`."""
    found = []
    for path in sorted(directory.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        for item in data['items']:
            item = dict(item, source=data['source'])
            item['slug'] = f"{data['source'].lower()}-{item['id']}"
            found.append(item)
    return found


def topic(repo):
    """How on topic a repository is: the number of chemistry subjects it was found under."""
    return len([s for s in repo['matched_subjects'] if s != 'Subject Agnostic'])


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def values(tree, key):
    question = tree.by_key(key)
    return [o['value'] for o in question.get('options', [])] if question else []


def data_type(repo, tree):
    text = ' '.join([repo['name'] or '', repo['description'] or '',
                     *repo['subjects'], *repo['domains']]).lower()
    if repo['scope'] == 'general':
        yes = values(tree, 'data_type')  # accepts any kind of data
    else:
        yes = [t for t, words in DATA_TYPE_WORDS.items() if any(w in text for w in words)]
    return {'yes': yes, 'info': [('Subjects', repo['subjects']),
                                 ('Domains', repo['domains'])]}


def license(repo, tree):
    names = [l['name'] for l in repo['licences'] if l['name']]
    yes = []
    if any('CC0' in n for n in names):
        yes.append('cc0')
    if any(re.search(r'\(CC BY [\d.]+\)', n) for n in names):
        yes.append('cc-by')
    return {'yes': yes, 'info': [('Licences', names)]}


def region(repo, tree):
    lower = [c.lower() for c in repo['countries']]
    places = [c for c in lower if c not in NOT_A_COUNTRY]
    yes, no = ['no'], []
    if lower and all(c in EU or c == 'european union' for c in lower):
        yes.append('eu')
    elif places and not any(c in EU for c in places) and 'european union' not in lower:
        no.append('eu')
    return {'yes': yes, 'no': no, 'info': [('Country', repo['countries'])]}


def country(repo, tree):
    ids = {slugify(c) for c in repo['countries']}
    real = {slugify(c) for c in repo['countries'] if c.lower() not in NOT_A_COUNTRY}
    listed = [i['id'] for i in tree.lists['countries']['items']]
    yes = [i for i in listed if i in ids]
    # A repository in one country is not in another, unless it says it is worldwide.
    no = [] if (not real or len(real) < len(ids)) else [i for i in listed if i not in real]
    return {'yes': yes, 'no': no, 'info': [('Country', repo['countries'])]}


def access(repo, tree):
    kind = (repo['data_access'] or {}).get('type')
    yes, no = [], []
    if kind in ('open', 'partially open'):
        yes.append('open')
    if kind == 'controlled':
        no.append('open')
    if kind == 'partially open':
        yes.append('embargo')
    if kind in ('controlled', 'partially open'):
        yes.append('restricted')
    if kind == 'open':
        no.append('restricted')
    info = []
    for label, condition in (('Data access', repo['data_access']),
                             ('Data deposition', repo['data_deposition'])):
        if condition and condition.get('type'):
            info.append((label, [condition['type'] + (
                ': ' + condition['notes'] if condition.get('notes') else '')]))
    return {'yes': yes, 'no': no, 'info': info}


def recommended(repo, tree):
    return {'info': [('Recommended by', [p['name'] for p in repo['recommended_by']])]}


def institution(repo, tree):
    return {'info': [('Organisations', [f"{o['name']} ({o['relation']})"
                                        for o in repo['organisations']])]}


FACTS = {
    'data_type': data_type, 'license': license, 'region': region, 'country': country,
    'access': access, 'journal_requirement': recommended, 'funder_requirement': recommended,
    'institutional_repository': institution,
}


def facts(repo, tree):
    """{answer_key: {'yes': [...], 'no': [...], 'info': [(label, [values])]}}"""
    found = {}
    for key, function in FACTS.items():
        fact = function(repo, tree)
        info = [(label, vals) for label, vals in fact.get('info', []) if vals]
        found[key] = {'yes': fact.get('yes', []), 'no': fact.get('no', []), 'info': info}
    return found
