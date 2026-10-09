// Remembers the answers of a visit in sessionStorage, so the end of the
// decision tree can use them. Without JavaScript the questions still work.
(function () {
  var KEY = 'chemrepos-answers';
  function load() {
    try { return JSON.parse(sessionStorage.getItem(KEY)) || {}; } catch (e) { return {}; }
  }
  function save(answers) {
    try { sessionStorage.setItem(KEY, JSON.stringify(answers)); } catch (e) {}
  }

  document.addEventListener('click', function (event) {
    var link = event.target.closest('a');
    if (!link) return;
    if (link.hasAttribute('data-restart')) return save({});
    if (!link.dataset.key) return;
    var answers = load();
    answers[link.dataset.key] = {value: link.dataset.value, label: link.dataset.label};
    save(answers);
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

  var list = document.getElementById('answers');
  if (list) {
    var answers = load();
    Object.keys(answers).forEach(function (key) {
      var item = document.createElement('li');
      item.textContent = key.replace(/_/g, ' ') + ': ' + answers[key].label;
      list.appendChild(item);
    });
  }
})();
