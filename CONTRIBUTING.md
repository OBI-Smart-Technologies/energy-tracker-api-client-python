# Contributing

Thanks for taking the time to contribute. This library is the API layer of the
[OBI ENERGY TRACKER Home Assistant integration](https://github.com/FabiNaryOBI/ha-obi-energy-tracker),
so a change here can reach every Home Assistant user of the integration.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Development setup

```bash
python3.14 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Checks

All four have to pass before a pull request can be merged; CI runs exactly these:

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/mypy
```

Tests also run against the oldest supported Python (3.13) in CI.

## Ground rules

- **No Home Assistant imports.** The library must stay usable without Home Assistant.
  Anything that needs `homeassistant` belongs in the integration repository.
- **Async only.** No blocking I/O, no `requests`, no thread pools. The caller supplies the
  `aiohttp.ClientSession`; the library never creates or closes one.
- **Fully typed.** `mypy --strict` is clean and `py.typed` is shipped, so consumers get
  the types. New public functions need annotations, not `Any`.
- **Unknown values do not escape.** A `state`, `measure` or
  `otaStatus` the library does not know parses to `None` or is dropped. Never pass a raw
  backend string to the caller.
- **Every request carries an explicit timeout.** A shared session's default is far too
  coarse to rely on.
- **Tests need no network.** `tests/conftest.py` starts a real local `aiohttp` server
  (`FakeBackend`); queue responses with `backend.respond(...)` and assert on
  `backend.requests`. Do not add an HTTP mocking dependency — `aioresponses` breaks
  whenever `aiohttp` changes its internals.
- **Keep the public surface small.** `__init__.py`'s `__all__` is the contract; everything
  else is an implementation detail and may change in a patch release.

## Pull requests

1. Branch off `main` (`feat/…`, `fix/…`, `docs/…`).
2. Keep the change focused, and add tests for it.
3. Add an entry under `## Unreleased` in [CHANGELOG.md](CHANGELOG.md).
4. Open the pull request and fill in the template.

## Versioning

[Semantic Versioning](https://semver.org/). The Home Assistant integration pins this
package exactly (`obi-energy-tracker==X.Y.Z` in its `manifest.json`), so any change to the
public surface has to be reflected in the version number:

- **major** — a removed or renamed public name, a changed signature, changed parsing
  semantics
- **minor** — new endpoints, new public helpers, new model fields
- **patch** — bug fixes and internals

## Releasing

Releases are cut manually by the repository owners; nothing is published on a push or a
merge.

The repository is licensed under the Apache License, Version 2.0; the copyright holder is
OBI Smart Technologies GmbH. Contributions are accepted under the same license (see
section 5 of the license). Do not remove `LICENSE` or `NOTICE` — the release workflow
refuses to run without a `LICENSE` file, and both files are shipped in the distribution
via `license-files` in `pyproject.toml`.

1. Bump `version` in `pyproject.toml` and rename the `## Unreleased` heading in
   `CHANGELOG.md` to `## X.Y.Z - YYYY-MM-DD`, leaving a fresh empty `## Unreleased` above
   it.
2. Merge that to `main`.
3. Run the **Release** workflow (Actions → Release → *Run workflow*) with `index=testpypi`
   first if the packaging changed, then with `index=pypi`. The workflow only runs on `main`.
4. The workflow builds the distribution, refuses to continue if `vX.Y.Z` is already
   tagged, waits for the `pypi` environment approval, publishes, and then creates the tag
   and the GitHub release.
