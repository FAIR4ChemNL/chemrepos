import unittest

from app import create_app, repositories
from app.tree import Tree


class TreeTest(unittest.TestCase):

    def test_real_tree_is_valid(self):
        self.assertEqual(Tree.load().problems(), [])

    def question(self, id, **kw):
        return {'id': id, '_file': id + '.json', 'title': id, 'type': 'choice',
                'answer_key': id, **kw}

    def test_problems(self):
        a = self.question('a', start=True, options=[
            {'value': 'x', 'label': 'X', 'next': 'b'},
            {'value': 'y', 'label': 'Y', 'next': 'missing'}])
        b = self.question('b', options=[{'value': 'x', 'label': 'X', 'next': 'a'}])
        c = self.question('c', type='end')
        problems = Tree({'a': a, 'b': b, 'c': c}, {}).problems()
        self.assertIn('a.json: unknown question "missing"', problems)
        self.assertIn('loop: a -> b -> a', problems)
        self.assertIn('c: cannot be reached from the start', problems)


class AppTest(unittest.TestCase):

    def setUp(self):
        self.client = create_app().test_client()

    def test_index_links_to_start(self):
        page = self.client.get('/').get_data(as_text=True)
        self.assertIn('href="/question/data-type/"', page)

    def test_every_question_renders(self):
        for question_id in create_app().config['TREE'].questions:
            response = self.client.get(f'/question/{question_id}/')
            self.assertEqual(response.status_code, 200, question_id)

    def test_choice_links_to_next(self):
        page = self.client.get('/question/journal-requirement/').get_data(as_text=True)
        self.assertIn('href="/question/publisher/"', page)

    def test_search_lists_items(self):
        page = self.client.get('/question/publisher/').get_data(as_text=True)
        self.assertIn('Royal Society of Chemistry', page)
        self.assertIn('href="/question/funder-requirement/"', page)

    def test_steps_have_back_and_skip(self):
        page = self.client.get('/question/size/').get_data(as_text=True)
        self.assertIn('id="back"', page)
        self.assertIn('href="/question/results/" data-skip', page)
        end = self.client.get('/question/results/').get_data(as_text=True)
        self.assertNotIn('data-skip', end)
        self.assertIn('id="repository-data"', end)

    def test_every_repository_has_a_page_with_the_questions(self):
        app = create_app()
        client = app.test_client()
        for repo in app.config['REPOSITORIES']:
            page = client.get(f"/repository/{repo['slug']}/")
            self.assertEqual(page.status_code, 200, repo['slug'])
        text = page.get_data(as_text=True).replace('&#39;', "'")
        for question in app.config['TREE'].order():
            self.assertIn(question['title'], text)

    def test_doi_only_when_fairsharing_has_one(self):
        app = create_app()
        client = app.test_client()
        with_doi = next(r for r in app.config['REPOSITORIES'] if r['fairsharing_doi'])
        without = next(r for r in app.config['REPOSITORIES'] if not r['fairsharing_doi'])
        page = client.get(f"/repository/{with_doi['slug']}/").get_data(as_text=True)
        self.assertIn(f"https://doi.org/{with_doi['fairsharing_doi']}", page)
        page = client.get(f"/repository/{without['slug']}/").get_data(as_text=True)
        self.assertNotIn('doi.org/10.25504', page)  # the footer links to another DOI

    def test_overview_and_404(self):
        self.assertEqual(self.client.get('/tree/').status_code, 200)
        self.assertEqual(self.client.get('/question/nope/').status_code, 404)


class FactsTest(unittest.TestCase):

    def setUp(self):
        self.tree = Tree.load()

    def repo(self, **kw):
        return {'name': 'R', 'description': '', 'subjects': [], 'domains': [],
                'countries': [], 'licences': [], 'scope': 'chemistry',
                'data_access': None, 'data_deposition': None,
                'recommended_by': [], 'organisations': [], **kw}

    def test_country(self):
        found = repositories.country(self.repo(countries=['Germany']), self.tree)
        self.assertEqual(found['yes'], ['germany'])
        self.assertNotIn('germany', found['no'])
        self.assertIn('netherlands', found['no'])
        worldwide = repositories.country(self.repo(countries=['Worldwide']), self.tree)
        self.assertEqual((worldwide['yes'], worldwide['no']), ([], []))

    def test_region(self):
        self.assertIn('eu', repositories.region(self.repo(countries=['France']), self.tree)['yes'])
        self.assertIn('eu', repositories.region(self.repo(countries=['Canada']), self.tree)['no'])
        self.assertEqual(repositories.region(self.repo(), self.tree)['no'], [])

    def test_license_keeps_licences_apart(self):
        names = [{'name': 'Creative Commons Attribution 4.0 International (CC BY 4.0)'},
                 {'name': 'Creative Commons (CC) Public Domain Mark (PDM)'}]
        found = repositories.license(self.repo(licences=names), self.tree)
        self.assertEqual(found['yes'], ['cc-by'])

    def test_access(self):
        found = repositories.access(self.repo(data_access={'type': 'controlled'}), self.tree)
        self.assertIn('open', found['no'])
        self.assertIn('restricted', found['yes'])

    def test_order_has_no_end(self):
        order = [q['id'] for q in self.tree.order()]
        self.assertEqual(order[0], 'data-type')
        self.assertNotIn('results', order)


if __name__ == '__main__':
    unittest.main()
