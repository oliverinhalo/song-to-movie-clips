from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from ..mixer import MixLevels, render_mix


def create_app(project_dir: Path) -> Flask:
    """Serve a small local mixing console for one pipeline run's output.

    `project_dir` must already contain `clips_only.mp4` and a `stems/`
    subdirectory, both produced by `song_to_movie.cli.run_pipeline(...,
    render_default_mix=False)`. The page previews the three elements
    (movie clips, vocals, instrumental) with independent volume sliders and
    can export the chosen blend via ffmpeg.
    """
    project_dir = Path(project_dir)
    clip_video = project_dir / "clips_only.mp4"
    vocals = next((project_dir / "stems").rglob("vocals.wav"), None)
    instrumental = next((project_dir / "stems").rglob("no_vocals.wav"), None)
    if not clip_video.exists() or vocals is None or instrumental is None:
        raise RuntimeError(
            f"{project_dir} is missing clips_only.mp4 or stems/*.wav - run "
            "the pipeline with render_default_mix=False first"
        )

    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template("mixer.html")

    @app.route("/media/<name>")
    def media(name: str):
        paths = {"clips": clip_video, "vocals": vocals, "instrumental": instrumental}
        if name not in paths:
            return ("not found", 404)
        return send_file(paths[name])

    @app.route("/export", methods=["POST"])
    def export():
        data = request.get_json(force=True)
        levels = MixLevels(
            vocals=float(data.get("vocals", 1.0)),
            instrumental=float(data.get("instrumental", 1.0)),
            clips=float(data.get("clips", 1.0)),
        )
        out_path = project_dir / "final_mix.mp4"
        render_mix(clip_video, vocals, instrumental, out_path, levels=levels)
        return jsonify({"path": str(out_path)})

    return app
