# Contributing to dbcomparer

Thanks for your interest!

## Reporting bugs and asking for help

Open an issue at https://github.com/rairs/dbcomparer/issues. Include the
dbcomparer version, the database engines and versions, the command you ran,
and the output you got. Questions are welcome as issues too.

## Development setup

```bash
git clone https://github.com/rairs/dbcomparer && cd dbcomparer
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
```

## Pull requests

1. Fork the repo and create a branch.
2. Add tests for any new behaviour (`tests/`).
3. Make sure `pytest` and `ruff check .` pass.
4. Open a pull request describing the change.

All participants are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
