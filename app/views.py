from flask import Blueprint, abort, current_app, render_template, url_for

from . import repositories

main = Blueprint('app', __name__)


def tree():
    return current_app.config['TREE']


def repos():
    return current_app.config['REPOSITORIES']


@main.route('/')
def index():
    return render_template('index.html', start=tree().start)


@main.route('/question/<question_id>/')
def question(question_id):
    current = tree().questions.get(question_id)
    if current is None:
        abort(404)
    items, summary = [], []
    if current['type'] == 'search':
        items = tree().lists[current['list']]['items']
    if current['type'] == 'end':
        # What the page needs to match the repositories with the answers, in the browser.
        summary = [{'url': url_for('app.repository', slug=r['slug']), 'name': r['name'], 'abbreviation': r['abbreviation'],
                    'scope': r['scope'], 'providers': [p['name'] for p in r['providers']],
                    'documentation': repositories.documentation_sources(r), 'topic': repositories.topic(r), 'countries': r['countries'],
                    'yes': {k: f['yes'] for k, f in repositories.facts(r, tree()).items()},
                    'no': {k: f['no'] for k, f in repositories.facts(r, tree()).items()}}
                   for r in repos()]
    kinds = {o['value']: o['label']
             for o in (tree().by_key('data_type') or {}).get('options', [])}
    return render_template('question.html', question=current, items=items,
                           repositories=summary, end=tree().end, kinds=kinds)


@main.route('/repository/<slug>/')
def repository(slug):
    found = next((r for r in repos() if r['slug'] == slug), None)
    if found is None:
        abort(404)
    return render_template('repository.html', repo=found, end=tree().end,
                           questions=tree().order(), facts=repositories.facts(found, tree()),
                           lists=tree().lists)


@main.route('/repositories/')
def repository_list():
    return render_template('repositories.html', repos=repos())


@main.route('/about/')
def about():
    return render_template('about.html', sources=repositories.sources(), total=len(repos()))


@main.route('/tree/')
def overview():
    return render_template('tree.html', questions=tree().questions.values(),
                           start=tree().start)


@main.app_errorhandler(404)
def not_found(error):
    return render_template('error.html'), 404
