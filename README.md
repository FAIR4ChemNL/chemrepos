# Find a data repository

A website that helps researchers (chemistry first) find a repository to archive their data. The
visitor answers a series of questions, which form a decision tree. Some questions are a choice
between a few options, others search a list (publishers, funders, institutions, ...).

The website is a small [Flask](https://flask.palletsprojects.com/) application, published as
static HTML with Frozen-Flask. It is based on the setup in [background/polymers/](background/polymers/).

## The decision tree

Every question is one JSON file in [questions/](questions/), named after its `id`. The structure of
the tree is **only** in the metadata of these files: add, remove or rewire questions by editing
them; no code changes are needed.

| field | meaning |
|---|---|
| `id` | the identifier; equals the file name without `.json` |
| `type` | `choice` (pick an option), `search` (pick an item from a list) or `end` (a result, nothing follows) |
| `start` | `true` on exactly one question: where the visitor begins |
| `title`, `help` | the question and an optional explanation |
| `answer_key` | the name under which the answer is remembered, for filtering the repositories later |
| `options` | for a `choice`: a list of `{value, label, description, next}` |
| `list` | for a `search`: the name of a file in [_data/lists/](_data/lists/) |
| `next` | the question that follows. On a `search` it is used for every item; on a `choice` it is the default for options without their own `next` |
| `placeholder` | for a `search`: the text in the search box |

A list item is `{id, label, aliases, next}`; `aliases` are extra words that find the item and a
`next` on an item overrides the one of the question. Fields that are not listed here are ignored
by the website, so extra metadata (for example what an answer means for the choice of repository)
can be added to questions, options and list items as needed.

Run

```shell
make check
```

to find broken links, unreachable questions, loops, and missing lists. The page `/tree/` of the
website lists all questions and where they lead to.

The answers of a visitor are kept in the browser (`sessionStorage`) and shown at the end; matching
the answers to repositories is not built yet.

## Running it

Requires Python 3.

```shell
make venv      # create venv/ and install the requirements
make serve     # run the website at http://localhost:8200/
make check     # check the questions
make build     # check, then write the static website to build/
make test      # run the tests
```

## License

The code is released under the GNU General Public License version 3, see [LICENSE.md](LICENSE.md).

## Use of LLMs

This web application is created with the help of LLMs, but the authors take full responsibility of all functionality.
