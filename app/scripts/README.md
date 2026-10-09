# Maintenance commands

Run Python commands from the application directory with `python -m
scripts.<group>.<command>`, using the environment documented for that command.
Packages contain setup, catalog, models, training, skills, integrations, audit,
verification and preview programs. See the [complete folder map](../docs/project-structure.md).

For ordinary regression/readiness checks, use `python -m unittest discover -s
tests -q` and `python -m jarvis.launcher --check`. Individual verification scripts
retain their original fixture, local-inference, UI or live-account behavior; they
are not one blanket smoke-test command.
