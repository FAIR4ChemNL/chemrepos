import unittest

from app import create_app
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

    def test_overview_and_404(self):
        self.assertEqual(self.client.get('/tree/').status_code, 200)
        self.assertEqual(self.client.get('/question/nope/').status_code, 404)


if __name__ == '__main__':
    unittest.main()
