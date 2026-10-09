from flask import Flask

from .tree import ROOT, Tree


def create_app(tree=None):
    app = Flask(__name__)
    # Relative links, so the frozen site works under any GitHub Pages path.
    app.config['FREEZER_RELATIVE_URLS'] = True
    app.config['FREEZER_DESTINATION'] = str(ROOT / 'build')
    app.config['TREE'] = tree or Tree.load()

    from .views import main
    app.register_blueprint(main)

    return app
