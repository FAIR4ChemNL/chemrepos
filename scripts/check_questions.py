"""Checks the decision tree in questions/. Run it with `make check`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tree import Tree  # noqa: E402


def main():
    tree = Tree.load()
    problems = tree.problems()
    for problem in problems:
        print(problem)
    print(f'{len(tree.questions)} questions, {len(tree.lists)} lists, '
          f'{len(problems)} problems')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
