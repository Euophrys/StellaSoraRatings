# Stella Sora Ratings

## Start the server

From the repo root:

```bash
source .venv/bin/activate
python -m ssr.web
```

This serves the build guide at <http://127.0.0.1:8765/> and opens it in your browser. Press `Ctrl+C` to stop it.

Options:

- `--port 9000`: use a different port
- `--no-open`: don't open the browser

## First-time setup

If `.venv` doesn't exist yet (requires Python 3.13+):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```
