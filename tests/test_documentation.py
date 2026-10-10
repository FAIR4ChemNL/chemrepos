import json
import re
import sys
from collections import Counter
import tempfile
import unittest
from pathlib import Path

from app import create_app, repositories

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import collect_biotools  # noqa: E402
import collect_fair4chemnl  # noqa: E402
import documentation_common as docs  # noqa: E402


def repo(slug, name, homepage, abbreviation=None):
    return {'slug': slug, 'name': name, 'homepage': homepage, 'abbreviation': abbreviation}


class MatchTest(unittest.TestCase):

    def test_biotools_by_website_or_name(self):
        repos = [repo('r-1', 'ChEMBL', 'https://www.ebi.ac.uk/chembl'),
                 repo('r-2', 'Other database', 'https://example.org/db/')]
        tools = [{'biotoolsID': 'chembl', 'name': 'ChEMBL', 'homepage': 'https://www.ebi.ac.uk/chembl/',
                  'documentation': [{'url': 'https://x/api', 'type': ['API documentation']},
                                    {'url': 'https://x/faq', 'type': ['FAQ']}]},
                 {'biotoolsID': 'o', 'name': 'Something', 'homepage': 'https://example.org/db/search'},
                 {'biotoolsID': 'e', 'name': 'ebi tool', 'homepage': 'https://www.ebi.ac.uk/other'}]
        found = collect_biotools.match_biotools(repos, tools)
        self.assertEqual([t['id'] for t in found['r-1']], ['chembl'])
        self.assertEqual(found['r-1'][0]['api_documentation'], ['https://x/api'])
        self.assertNotIn('r-2', found)  # a page below the repository is not the repository
        self.assertNotIn('e', [t['id'] for hits in found.values() for t in hits])

    def test_tess_by_link_or_title(self):
        repos = [repo('r-1', 'ChEMBL', 'https://x.org'), repo('r-2', 'Reactome pathways', 'https://y.org'),
                 repo('r-3', 'Short', 'https://z.org', 'ab')]
        entry = lambda i, title, **a: ({'id': i, 'links': {'self': f'/events/{i}'},  # noqa: E731
                                        'attributes': {'title': title, **a}}, 'https://tess')
        entries = [entry('1', 'Intro to ChEMBL'), entry('2', 'Other'),
                   entry('3', 'Chemblast'), entry('4', 'Workshop', **{
                       'external-resources': [{'title': 'x', 'url': 'https://bio.tools/tool/chembl'}]}),
                   entry('5', 'About ab and Short')]
        found = docs.match_tess(repos, entries, {'r-1': [{'id': 'chembl'}]})
        self.assertEqual({(e['id'], e['matched_on']) for e in found['r-1']},
                         {('1', 'text'), ('4', 'link')})
        self.assertEqual([e['id'] for e in found['r-3']], ['5'])
        self.assertNotIn('r-2', found)

    def test_text_match_is_exact_and_not_for_ordinary_words(self):
        repos = [repo('r-1', 'CORE', 'https://core.ac.uk'), repo('r-2', 'MetaboLights', 'https://x.org')]
        entry = lambda i, title, desc='': ({'id': i, 'links': {'self': f'/m/{i}'},  # noqa: E731
                                            'attributes': {'title': title, 'description': desc}}, 'h')
        entries = [entry(str(i), 'Setup', 'the core of it') for i in range(30)]
        entries += [entry('a', 'nf-core workflows'), entry('b', 'metabolights tutorial'),
                    entry('c', 'Using MetaboLights')]
        words = Counter()
        for e, _ in entries:
            words.update(re.findall(r'\b[A-Za-z]{3,}\b', e['attributes']['description']))
        found = docs.match_tess(repos, entries, {}, words)
        self.assertNotIn('r-1', found)  # 'core' is an ordinary word here
        self.assertEqual([e['id'] for e in found['r-2']], ['c'])  # exactly as written


class FairMaterialsTest(unittest.TestCase):

    def test_metadata_and_match(self):
        text = '---\nlayout: default\n\ntrainingMaterial:\n  "@id": https://x.org/1\n  name: "Zenodo use case"\n' \
               '  keywords: "repositories, dmp"\n  url: https://zenodo.org/help/\n---\n# Zenodo\n'
        material = collect_fair4chemnl.metadata(text)
        self.assertEqual(material['name'], 'Zenodo use case')
        self.assertEqual(collect_fair4chemnl.keywords_of(material), ['repositories', 'dmp'])
        repos = [repo('r-1', 'Zenodo', 'https://zenodo.org'), repo('r-2', 'Other', 'https://other.org')]
        found = collect_fair4chemnl.match(repos, [('1.md', material)], Counter())
        self.assertEqual(list(found), ['r-1'])
        self.assertEqual(found['r-1']['materials'][0]['id'], '1')


class SiteTest(unittest.TestCase):

    def test_badges_from_matches(self):
        with tempfile.TemporaryDirectory() as folder:
            real = repositories.load()
            first = real[0]['slug']
            (Path(folder) / 'bio.tools.json').write_text(json.dumps({'source': 'bio.tools', 'matches': {
                first: [{'id': 'x', 'name': 'X', 'url': 'https://bio.tools/x',
                         'api_documentation': [], 'matched_on': 'name'}]}}))
            (Path(folder) / 'taxila.json').write_text(json.dumps({'source': 'Taxila', 'matches': {
                first: {'events': [{'id': '1', 'title': 'Course', 'url': 'https://taxila.nl/events/1',
                                    'start': '2025-01-01T09:00:00Z', 'matched_on': 'text'}]}}}))
            loaded = repositories.load(documentation=Path(folder))
            self.assertEqual(repositories.documentation_sources(loaded[0]), ['bio.tools', 'Taxila'])
            self.assertEqual(repositories.documentation_sources(loaded[1]), [])
            app = create_app(repos=loaded)
            page = app.test_client().get(f'/repository/{first}/').get_data(as_text=True)
            self.assertIn('Course', page)
            self.assertIn('class="kind docs">Taxila', page)
            results = app.test_client().get('/question/results/').get_data(as_text=True)
            self.assertIn('"documentation": ["bio.tools", "Taxila"]', results)


if __name__ == '__main__':
    unittest.main()
