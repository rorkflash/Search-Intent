"""Start the sandbox:  uv run python -m sandbox  [--port 8090] [--no-browser]"""

from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn

from .server import DEFAULT_CONFIG_ROOT, create_app


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m sandbox",
        description="Browse, edit, create and test Search Intent config collections.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8090, help="default: 8090")
    parser.add_argument(
        "--config-root",
        default=str(DEFAULT_CONFIG_ROOT),
        help="folder holding one sub-folder per collection (default: ./config)",
    )
    parser.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    print(f"Search Intent sandbox: {url}")
    uvicorn.run(create_app(args.config_root), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
