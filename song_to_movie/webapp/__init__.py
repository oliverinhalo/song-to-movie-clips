from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from ..cli import run_pipeline
from ..mixer import MixLevels, render_mix

ALLOWED_SONG_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB


@dataclass
class RunState:
    """In-memory status for one upload -> processed-video run."""

    id: str
    title: str
    status: str = "queued"  # queued, running, done, error
    stage: str = ""
    error: Optional[str] = None
    project_dir: Optional[Path] = None
    created_at: float = field(default_factory=time.time)


def _discover_existing_runs(work_root: Path) -> Dict[str, RunState]:
    """Reconstruct completed runs from disk on startup.

    Run progress is only tracked in memory, so a restart of the web server
    while a run is mid-flight loses that run's status - but any run that
    already finished is still on disk under `work_root/<id>/output/` and is
    picked back up here rather than disappearing from the run list.
    """
    runs: Dict[str, RunState] = {}
    if not work_root.exists():
        return runs
    for run_dir in sorted(work_root.iterdir()):
        if not run_dir.is_dir():
            continue
        output_dir = run_dir / "output"
        if (output_dir / "clips_only.mp4").exists():
            runs[run_dir.name] = RunState(
                id=run_dir.name,
                title=run_dir.name,
                status="done",
                stage="done",
                project_dir=output_dir,
                created_at=run_dir.stat().st_mtime,
            )
    return runs


def _media_paths(project_dir: Path) -> Dict[str, Optional[Path]]:
    return {
        "clips": project_dir / "clips_only.mp4",
        "vocals": next((project_dir / "stems").rglob("vocals.wav"), None),
        "instrumental": next((project_dir / "stems").rglob("no_vocals.wav"), None),
    }


def create_app(work_root: Path) -> Flask:
    """Serve the full song_to_movie workflow from the browser.

    Upload a song + lyrics from any device on your network (e.g. your
    phone, reached over Tailscale), watch it process on this machine, then
    preview and export a vocals/instrumental/clips blend - no SSH access or
    CLI needed once the server is running. Each run's uploads and output
    live under `work_root/<run_id>/`.
    """
    work_root = Path(work_root)
    work_root.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    runs: Dict[str, RunState] = _discover_existing_runs(work_root)
    runs_lock = threading.Lock()

    def _execute_run(run_id: str, song_path: Path, lyrics_path: Path, out_dir: Path) -> None:
        state = runs[run_id]
        state.status = "running"
        try:
            run_pipeline(
                song_path=song_path,
                lyrics_path=lyrics_path,
                out_dir=out_dir,
                render_default_mix=False,
                on_progress=lambda stage: setattr(state, "stage", stage),
            )
            state.project_dir = out_dir
            state.status = "done"
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            state.status = "error"
            state.error = str(exc)

    @app.route("/")
    def index():
        ordered = sorted(runs.values(), key=lambda r: r.created_at, reverse=True)
        return render_template("index.html", runs=ordered)

    @app.route("/runs", methods=["POST"])
    def create_run():
        song_file = request.files.get("song")
        lyrics_text = (request.form.get("lyrics") or "").strip()
        title = (request.form.get("title") or "").strip()
        if not song_file or not song_file.filename:
            return ("a song audio file is required", 400)
        if not lyrics_text:
            return ("lyrics text is required", 400)

        suffix = Path(secure_filename(song_file.filename)).suffix.lower()
        if suffix not in ALLOWED_SONG_EXTENSIONS:
            return (
                f"unsupported audio type {suffix!r}; use one of "
                f"{sorted(ALLOWED_SONG_EXTENSIONS)}",
                400,
            )

        run_id = uuid.uuid4().hex[:12]
        run_dir = work_root / run_id
        input_dir = run_dir / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        song_path = input_dir / f"song{suffix}"
        song_file.save(song_path)
        lyrics_path = input_dir / "lyrics.txt"
        lyrics_path.write_text(lyrics_text)

        with runs_lock:
            runs[run_id] = RunState(id=run_id, title=title or song_file.filename)

        thread = threading.Thread(
            target=_execute_run,
            args=(run_id, song_path, lyrics_path, run_dir / "output"),
            daemon=True,
        )
        thread.start()
        return redirect(url_for("show_run", run_id=run_id))

    @app.route("/runs/<run_id>")
    def show_run(run_id: str):
        state = runs.get(run_id)
        if state is None:
            return ("run not found", 404)
        return render_template("run.html", run=state)

    @app.route("/runs/<run_id>/status.json")
    def run_status(run_id: str):
        state = runs.get(run_id)
        if state is None:
            return ("run not found", 404)
        return jsonify({"status": state.status, "stage": state.stage, "error": state.error})

    @app.route("/runs/<run_id>/media/<name>")
    def run_media(run_id: str, name: str):
        state = runs.get(run_id)
        if state is None or state.project_dir is None:
            return ("not found", 404)
        path = _media_paths(state.project_dir).get(name)
        if not path or not path.exists():
            return ("not found", 404)
        return send_file(path)

    @app.route("/runs/<run_id>/export", methods=["POST"])
    def export_run(run_id: str):
        state = runs.get(run_id)
        if state is None or state.project_dir is None or state.status != "done":
            return ("run is not ready to export", 400)
        data = request.get_json(force=True)
        levels = MixLevels(
            vocals=float(data.get("vocals", 1.0)),
            instrumental=float(data.get("instrumental", 1.0)),
            clips=float(data.get("clips", 1.0)),
        )
        media = _media_paths(state.project_dir)
        out_path = state.project_dir / "final_mix.mp4"
        try:
            render_mix(
                media["clips"], media["vocals"], media["instrumental"], out_path, levels=levels
            )
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            return jsonify({"error": str(exc)}), 500
        return jsonify({"download_url": url_for("download_run", run_id=run_id)})

    @app.route("/runs/<run_id>/download")
    def download_run(run_id: str):
        state = runs.get(run_id)
        if state is None or state.project_dir is None:
            return ("not found", 404)
        out_path = state.project_dir / "final_mix.mp4"
        if not out_path.exists():
            return ("no exported mix yet - use Export first", 404)
        return send_file(out_path, as_attachment=True, download_name=f"{run_id}.mp4")

    return app
