"""python -m ssr.web [--port 8765] [--no-open]: serve the build guide page on localhost."""
from __future__ import annotations

import argparse
import threading
import webbrowser

from ..data import GameData
from .server import make_server


def main(argv=None):
    ap = argparse.ArgumentParser(description="Stella Sora build guide page (localhost)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true", help="don't open the browser")
    a = ap.parse_args(argv)
    srv = make_server(GameData(), port=a.port)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"Build guide: {url}  (Ctrl+C to stop)", flush=True)
    if not a.no_open:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
