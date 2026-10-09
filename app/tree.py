"""The decision tree: one JSON file per question in questions/.

The structure of the tree is only in the metadata of those files, so it is
changed by editing them. See the README for the fields.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = ROOT / 'questions'
LISTS = ROOT / '_data' / 'lists'

TYPES = ('choice', 'search', 'end')


class Tree:

    def __init__(self, questions, lists):
        self.questions = questions  # id -> question, in file order
        self.lists = lists          # name -> {'title': ..., 'items': [...]}

    @classmethod
    def load(cls, questions_dir=QUESTIONS, lists_dir=LISTS):
        questions = {}
        for path in sorted(Path(questions_dir).glob('*.json')):
            question = json.loads(path.read_text(encoding='utf-8'))
            question.setdefault('id', path.stem)
            question['_file'] = path.name
            questions[question['id']] = question
        lists = {}
        for path in sorted(Path(lists_dir).glob('*.json')):
            lists[path.stem] = json.loads(path.read_text(encoding='utf-8'))
        return cls(questions, lists)

    @property
    def start(self):
        starts = [q for q in self.questions.values() if q.get('start')]
        return starts[0] if len(starts) == 1 else None

    def targets(self, question):
        """The ids of the questions that can follow a question."""
        found = [option['next'] for option in question.get('options', [])
                 if option.get('next')]
        if question.get('next'):
            found.append(question['next'])
        return found

    def reachable(self):
        """The ids of the questions that can be reached from the start."""
        seen, todo = set(), [self.start['id']] if self.start else []
        while todo:
            current = todo.pop()
            if current in seen or current not in self.questions:
                continue
            seen.add(current)
            todo.extend(self.targets(self.questions[current]))
        return seen

    def problems(self):
        """What is wrong with the tree, as a list of messages."""
        found = []
        starts = [q['id'] for q in self.questions.values() if q.get('start')]
        if len(starts) != 1:
            found.append(f'exactly one question must have "start": true, '
                         f'found {starts}')
        for question in self.questions.values():
            name, kind = question['_file'], question.get('type')
            if name != question['id'] + '.json':
                found.append(f'{name}: id is "{question["id"]}"')
            if kind not in TYPES:
                found.append(f'{name}: type must be one of {TYPES}')
            if not question.get('title'):
                found.append(f'{name}: no title')
            if kind != 'end' and question.get('answer_key') is None:
                found.append(f'{name}: no answer_key')
            if kind == 'choice' and not question.get('options'):
                found.append(f'{name}: a choice needs options')
            if kind == 'search' and question.get('list') not in self.lists:
                found.append(f'{name}: unknown list "{question.get("list")}"')
            if kind == 'end' and self.targets(question):
                found.append(f'{name}: an end has nothing that follows')
            values = [o.get('value') for o in question.get('options', [])]
            if len(values) != len(set(values)):
                found.append(f'{name}: option values are not unique')
            for option in question.get('options', []):
                if not option.get('label') or option.get('value') is None:
                    found.append(f'{name}: an option needs a label and value')
            if kind in ('choice', 'search'):
                for option in question.get('options', [question]):
                    if not option.get('next') and not question.get('next'):
                        found.append(f'{name}: nothing follows '
                                     f'"{option.get("value", "")}"')
            for target in self.targets(question):
                if target not in self.questions:
                    found.append(f'{name}: unknown question "{target}"')
        for name, data in self.lists.items():
            ids = [item.get('id') for item in data.get('items', [])]
            if not all(ids) or len(ids) != len(set(ids)):
                found.append(f'list {name}: items need unique ids')
        if len(starts) == 1:
            for missing in sorted(set(self.questions) - self.reachable()):
                found.append(f'{missing}: cannot be reached from the start')
            found.extend(self._loops())
        return found

    def _loops(self):
        found, state = [], {}

        def visit(current, path):
            if state.get(current) == 'done' or current not in self.questions:
                return
            if state.get(current) == 'busy':
                found.append('loop: ' + ' -> '.join(path[path.index(current):]))
                return
            state[current] = 'busy'
            for target in self.targets(self.questions[current]):
                visit(target, path + [target])
            state[current] = 'done'

        if self.start:
            visit(self.start['id'], [self.start['id']])
        return found
