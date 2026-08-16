from __future__ import annotations

import argparse
from pathlib import Path

from . import create_app


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the song_to_movie web app: upload a song + lyrics, watch it "
            "process, then preview and export a blend - all from the browser."
        )
    )
    parser.add_argument(
        "work_dir",
        type=Path,
        nargs="?",
        default=Path("runs"),
        help="directory to store uploads/output for each run (default: ./runs)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help=(
            "bind address - use 0.0.0.0 to reach this from another device "
            "(e.g. your phone over Tailscale). Default: 127.0.0.1, "
            "localhost only."
        ),
    )
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    app = create_app(args.work_dir)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
