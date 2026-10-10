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
SERVICES = ROOT / '_data' / 'services'
DOCUMENTATION = ROOT / '_data' / 'documentation'
DOCUMENTATION_SOURCES = ('bio.tools', 'TeSS', 'Taxila')

# Words in the subjects, name or description that suggest a type of data.
DATA_TYPE_WORDS = {
    'spectra': ['spectr', 'nmr', 'mass spec', 'infrared'],
    'crystal-structures': ['crystal', 'diffraction'],
    'computational': ['computational chem', 'quantum', 'molecular dynamics', 'simulation'],
    'catalysis': ['catalys', 'catalytic'],
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


# Addresses shared by many projects: a link to them says nothing about who offers a repository.
SHARED_HOSTS = {'github.com', 'gitlab.com', 'doi.org', 'zenodo.org', 'youtube.com',
                'github.io', 'w3id.org'}


SECOND_LEVEL = {'co.uk', 'ac.uk', 'org.uk', 'gov.uk', 'com.au', 'edu.au', 'org.au', 'ac.jp',
                'co.jp', 'ac.at', 'co.at', 'com.br', 'ac.za', 'co.za', 'com.cn', 'edu.cn'}


def address(url):
    """An address without scheme, www, query and trailing slash, for comparing."""
    return re.sub(r'^[a-z]+:(//)?(www\.)?|[?#].*$|/+$', '', (url or '').strip().lower())


def same_resource(homepage, link):
    """Whether a homepage and the link of a service are the same website or a part of it.

    The same address, a page below the address of the link, or a website of its own
    (like radar4chem.radar-service.eu) of which the link is the front door. A website
    of an institute with many resources (like ebi.ac.uk) is not enough.
    """
    home, link = address(homepage), address(link)
    if not home or not link:
        return False
    host, _, path = link.partition('/')
    if host in SHARED_HOSTS:
        return False
    if home == link or (path and home.startswith(link + '/')):
        return True
    labels = host.split('.')
    own_site = len(labels) >= 3 and '.'.join(labels[-2:]) not in SECOND_LEVEL
    return not path and own_site and home.partition('/')[0] == host


def providers(repo, services):
    """The service providers (like NFDI4Cat) that offer this repository as a service.

    A repository belongs to a provider when its homepage is the website of one of the
    provider's services, or when it has exactly the name of one of them.
    """
    found = []
    for provider in services:
        for service in provider['items']:
            links = [link['url'] for link in service['links']] + [service['url']]
            if (any(same_resource(repo.get('homepage'), link) for link in links)
                    or slugify(repo['name'] or '') == slugify(service['name'])):
                found.append({'name': provider['source'], 'service': service['name'],
                              'url': service['url']})
    return found


def load(directory=REPOSITORIES, services=SERVICES, documentation=DOCUMENTATION):
    """All repositories of all sources, each with a `slug`, its `source` and `providers`."""
    offered = [data for data in (json.loads(p.read_text(encoding='utf-8'))
                                 for p in sorted(services.glob('*.json'))) if 'items' in data]
    docs = {}  # slug -> {catalogue: entries}, from the file of each catalogue
    for path in sorted(documentation.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        for slug, entries in data['matches'].items():
            docs.setdefault(slug, {})[data['source']] = entries
    found = []
    for path in sorted(directory.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        for item in data['items']:
            item = dict(item, source=data['source'])
            item['slug'] = f"{data['source'].lower()}-{item['id']}"
            item['providers'] = providers(item, offered)
            item['documentation'] = docs.get(item['slug'], {})
            found.append(item)
    return found


def sources(directory=REPOSITORIES, services=SERVICES, documentation=DOCUMENTATION):
    """What each data file says about itself, for the About page: the repositories, the
    services of providers, and the catalogues with documentation."""
    def read(folder):
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('*.json'))]
    providers_ = [{'name': d['source'], 'url': d.get('url'), 'retrieved': d.get('retrieved'),
                   'collected_from': d.get('collected_from'),
                   'count': sum(1 for i in d['items'] if not i.get('documentation'))}
                  for d in read(services) if 'items' in d]
    return {
        'repositories': [{'name': d['source'], 'url': d.get('url'), 'licence': d.get('licence'),
                          'retrieved': d.get('retrieved'), 'count': len(d['items'])}
                         for d in read(directory)],
        'providers': providers_,
        'documentation': [{'name': d['source'], 'url': d.get('url'), 'retrieved': d.get('retrieved'),
                           'entries': d['entries'], 'count': len(d['matches'])}
                          for d in read(documentation)],
    }


def topic(repo):
    """How on topic a repository is: the number of chemistry subjects it was found under."""
    return len([s for s in repo['matched_subjects'] if s != 'Subject Agnostic'])


def documentation_sources(repo):
    """The documentation catalogues (bio.tools, TeSS, Taxila) with entries for a repository."""
    return [name for name in DOCUMENTATION_SOURCES if repo.get('documentation', {}).get(name)]


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def values(tree, key):
    question = tree.by_key(key)
    return [o['value'] for o in question.get('options', [])] if question else []


def data_type(repo, tree):
    text = ' '.join([repo['name'] or '', repo['description'] or '',
                     *repo['subjects'], *repo['domains'],
                     *repo.get('user_defined_tags', [])]).lower()
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
