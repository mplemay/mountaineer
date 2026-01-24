# ci-webapp

An example webapp, built with mountaineer.
This is intended for CI use only, to test edge cases more easily served by a fully functioning webapp.

## Getting Started

We link to the local version of mountaineer in `pyproject.toml`.
On the first install it should fetch dependencies with poetry and then build the rust components with maturin.

```bash
poetry install
(cd my_website/views && npm install)

poetry run runserver
```

If doing concurrent development in the main codebase, you will have to manually restart the `runserver` command.
Python changes in the main package will be picked up - but you'll need to rebuild rust artifacts with maturin.
See the main README for instructions on how to do this.

Changes in the my_website codebase should be automatically picked up.
