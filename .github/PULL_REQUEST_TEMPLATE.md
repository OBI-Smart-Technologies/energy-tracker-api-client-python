## What does this change?

<!-- One or two sentences, and the issue it closes. -->

## Type of change

- [ ] Bug fix (no public API change)
- [ ] New feature (new public name, backwards compatible)
- [ ] Breaking change (public name removed, renamed or behaving differently)
- [ ] Documentation or tooling only

## Checklist

- [ ] `pytest` passes
- [ ] `ruff check src tests` and `ruff format --check src tests` pass
- [ ] `mypy` passes
- [ ] Tests cover the change
- [ ] No `homeassistant` import was added
- [ ] `CHANGELOG.md` has an entry under `## Unreleased`
- [ ] The public surface in `__init__.py` (`__all__`) is up to date
