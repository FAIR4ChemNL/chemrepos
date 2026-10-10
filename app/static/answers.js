// Remembers the answers of a visit in sessionStorage: for the Back link, for the
// list of matching repositories at the end, and for marking them on repository
// pages. Without JavaScript the questions still work, but there is no Back link
// and no list of repositories.
(function () {
  var KEY = 'chemrepos-answers';
  var body = document.body;

  // answers: answer_key -> {value, label, question}; path: the questions answered
  // or skipped, in order.
  function load() {
    try {
      var state = JSON.parse(sessionStorage.getItem(KEY)) || {};
      return {answers: state.answers || {}, path: state.path || []};
    } catch (e) { return {answers: {}, path: []}; }
  }
  function save(state) {
    try { sessionStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
  }
  // Question pages are siblings: .../question/<id>/
  function questionUrl(id) { return location.pathname.replace(/[^/]+\/$/, id + '/'); }

  var state = load();
  var current = body.dataset.question;

  // Arriving at a question (also with the browser's back button) forgets the
  // answers from that question onwards.
  var at = state.path.indexOf(current);
  if (current && at >= 0) {
    var dropped = state.path.splice(at);
    Object.keys(state.answers).forEach(function (key) {
      if (dropped.indexOf(state.answers[key].question) >= 0) delete state.answers[key];
    });
    save(state);
  }

  var back = document.getElementById('back');
  if (back && state.path.length) {
    back.href = questionUrl(state.path[state.path.length - 1]);
    back.hidden = false;
  }

  document.addEventListener('click', function (event) {
    var link = event.target.closest('a');
    if (!link) return;
    if (link.hasAttribute('data-restart')) return save({answers: {}, path: []});
    if (link.hasAttribute('data-skip') && current) {
      state.path.push(current);
      return save(state);
    }
    if (!link.dataset.key || !current) return;
    state.answers[link.dataset.key] = {
      value: link.dataset.value, label: link.dataset.label, question: current};
    state.path.push(current);
    save(state);
  });

  var filter = document.getElementById('filter');
  if (filter) {
    var items = document.querySelectorAll('#results li');
    filter.addEventListener('input', function () {
      var text = filter.value.trim().toLowerCase();
      items.forEach(function (item) {
        item.hidden = text !== '' && item.firstElementChild.dataset.search.indexOf(text) < 0;
      });
    });
  }

  function add(parent, tag, text, className) {
    var element = document.createElement(tag);
    element.textContent = text;
    if (className) element.className = className;
    parent.appendChild(element);
    return element;
  }

  // The end: the answers, and the repositories that fit them.
  var list = document.getElementById('answers');
  if (list) {
    var keys = Object.keys(state.answers);
    keys.forEach(function (key) {
      add(list, 'li', key.replace(/_/g, ' ') + ': ' + state.answers[key].label);
    });
    document.getElementById('no-answers').hidden = keys.length > 0;

    var repos = JSON.parse(document.getElementById('repository-data').textContent);
    var rated = repos.map(function (repo) {
      var yes = 0, unknown = 0, excluded = false;
      keys.forEach(function (key) {
        var value = state.answers[key].value;
        if ((repo.no[key] || []).indexOf(value) >= 0) excluded = true;
        else if ((repo.yes[key] || []).indexOf(value) >= 0) yes++;
        else unknown++;
      });
      return {repo: repo, yes: yes, unknown: unknown, excluded: excluded};
    }).filter(function (r) { return !r.excluded; }).sort(function (a, b) {
      return b.yes - a.yes || b.repo.topic - a.repo.topic || a.repo.name.localeCompare(b.repo.name);
    });
    var general = document.getElementById('general');
    var target = document.getElementById('repositories');
    document.getElementById('general-count').textContent =
      rated.filter(function (r) { return r.repo.scope === 'general'; }).length;

    // The kind of data is the most important question: show how the repository fits it.
    var labels = JSON.parse(document.getElementById('kind-labels').textContent);
    function kindBadges(item, repo) {
      var kinds = repo.yes.data_type || [], answer = state.answers.data_type;
      if (answer && answer.value !== 'other') {
        if (kinds.indexOf(answer.value) >= 0) add(item, 'span', answer.label, 'kind match');
        else add(item, 'span', 'kind of data not known', 'kind unknown');
      } else if (repo.scope === 'general') {
        add(item, 'span', 'any kind of data', 'kind');
      } else {
        kinds.forEach(function (kind) { add(item, 'span', labels[kind], 'kind'); });
      }
    }

    function render() {
      target.textContent = '';
      var shown = rated.filter(function (r) { return general.checked || r.repo.scope !== 'general'; });
      document.getElementById('count').textContent =
        '(' + shown.length + ' of ' + repos.length + ')';
      shown.forEach(function (r) {
        var item = add(target, 'li', '');
        var a = add(item, 'a', r.repo.name);
        a.href = r.repo.url;
        r.repo.providers.forEach(function (name) { add(item, 'span', name, 'kind provider'); });
        r.repo.documentation.forEach(function (name) { add(item, 'span', name, 'kind docs'); });
        kindBadges(item, r.repo);
        var detail = r.repo.countries.join(', ') + (r.repo.scope === 'general' ? ' · any subject' : '');
        if (keys.length) detail += ' · supports ' + r.yes + ' of ' + keys.length + ' answers';
        add(item, 'span', detail, 'muted');
      });
    }
    general.addEventListener('change', render);
    render();
  }

  // A repository page: mark what the visitor answered.
  var sections = document.querySelectorAll('.fit');
  sections.forEach(function (section) {
    var answer = state.answers[section.dataset.key];
    if (!answer) return;
    document.getElementById('visitor').hidden = false;
    var yes = JSON.parse(section.dataset.yes), no = JSON.parse(section.dataset.no);
    var verdict = no.indexOf(answer.value) >= 0 ? 'this repository is not compatible'
      : yes.indexOf(answer.value) >= 0 ? 'this repository supports it' : 'not known for this repository';
    var line = section.querySelector('.answer');
    line.textContent = 'Your answer: ' + answer.label + ' – ' + verdict;
    line.hidden = false;
    section.querySelectorAll('li[data-value]').forEach(function (li) {
      if (li.dataset.value === answer.value) li.classList.add('chosen');
    });
  });
})();
