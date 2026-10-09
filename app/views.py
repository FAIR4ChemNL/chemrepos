from flask import Blueprint, abort, current_app, render_template

main = Blueprint('app', __name__)


def tree():
    return current_app.config['TREE']


@main.route('/')
def index():
    return render_template('index.html', start=tree().start)


@main.route('/question/<question_id>/')
def question(question_id):
    current = tree().questions.get(question_id)
    if current is None:
        abort(404)
    items = []
    if current['type'] == 'search':
        items = tree().lists[current['list']]['items']
    return render_template('question.html', question=current, items=items)


@main.route('/tree/')
def overview():
    return render_template('tree.html', questions=tree().questions.values(),
                           start=tree().start)


@main.app_errorhandler(404)
def not_found(error):
    return render_template('error.html'), 404
