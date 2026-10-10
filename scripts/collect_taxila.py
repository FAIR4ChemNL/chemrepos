"""Finds the training materials and events of Taxila (https://taxila.nl)
for the repositories in _data/repositories/. Run it with `make collect-taxila`.

The catalogue is downloaded completely (the answers of the API are cached as they
are in cache/documentation/Taxila/) and searched here, so `--from-cache` redoes the
matching without downloading. The result is _data/documentation/taxila.json.

A repository matches an entry that links to its bio.tools entry (run collect_biotools.py
first), or that has the name or abbreviation of the repository, exactly as written, in
its title, keywords or linked resources. A name that is an ordinary word is not searched.
"""

import sys

from documentation_common import run_tess_like

if __name__ == '__main__':
    sys.exit(run_tess_like('Taxila', __doc__))
