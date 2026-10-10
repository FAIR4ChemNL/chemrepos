from flask import Flask

from . import repositories
from .tree import ROOT, Tree


def create_app(tree=None, repos=None):
    app = Flask(__name__)
    # Relative links, so the frozen site works under any GitHub Pages path.
    app.config['FREEZER_RELATIVE_URLS'] = True
    app.config['FREEZER_DESTINATION'] = str(ROOT / 'build')
    app.config['TREE'] = tree or Tree.load()
    app.config['REPOSITORIES'] = repositories.load() if repos is None else repos

    app.jinja_env.globals['documentation_sources'] = repositories.documentation_sources

    from .views import main
    app.register_blueprint(main)

    return app
