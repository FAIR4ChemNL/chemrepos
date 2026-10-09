"""Writes the website as static HTML files to build/, for GitHub Pages."""

from pathlib import Path

from flask_frozen import Freezer

from app import create_app

app = create_app()
freezer = Freezer(app)


@freezer.register_generator
def question():
    for question_id in app.config['TREE'].questions:
        yield 'app.question', {'question_id': question_id}


@freezer.register_generator
def repository():
    for repo in app.config['REPOSITORIES']:
        yield 'app.repository', {'slug': repo['slug']}


if __name__ == '__main__':
    freezer.freeze()
    # GitHub Pages should serve the files as they are, without Jekyll.
    (Path(app.config['FREEZER_DESTINATION']) / '.nojekyll').touch()
