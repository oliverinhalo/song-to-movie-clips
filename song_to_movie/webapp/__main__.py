from __future__ import annotations

import sys
from pathlib import Path

from . import create_app


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m song_to_movie.webapp <output_dir>")
        raise SystemExit(1)
    app = create_app(Path(sys.argv[1]))
    app.run(debug=False, port=5000)


if __name__ == "__main__":
    main()
