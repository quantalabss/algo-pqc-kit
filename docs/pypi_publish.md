# Publishing to PyPI

This guide outlines the steps to publish `algo-pqc-kit` to the Python Package Index (PyPI).

## Prerequisites

1. Ensure you have a PyPI account.
2. If QuantaLabs does not already own the `algo-pqc-kit` package name, you will register it upon first publish.
3. Generate an API token from your PyPI account settings.

## Steps

### 1. Version Bump
Ensure the `version` field in `pyproject.toml` is correct (e.g., `0.1.1` or `0.2.0-alpha`).
Do not publish `1.0.0` until the library is stable and audited.

### 2. Build the Package
Run the following commands from the project root to generate the distribution files:
```bash
pip install build twine
python -m build
```
This creates a `dist/` directory containing a `.tar.gz` (sdist) and a `.whl` (wheel) file.

### 3. Upload to PyPI
Use `twine` to securely upload the distribution files:
```bash
twine upload dist/*
```
You will be prompted for your PyPI username (use `__token__`) and your API token.

### 4. Verify Release
Once uploaded, verify the package is visible at `https://pypi.org/project/algo-pqc-kit/`.
You can now test installing it in a fresh virtual environment:
```bash
pip install algo-pqc-kit
```
