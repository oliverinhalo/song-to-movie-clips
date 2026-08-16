import io
import time

import song_to_movie.webapp as webapp_module


def _fake_run_pipeline(song_path, lyrics_path, out_dir, **kwargs):
    """Stand-in for the real pipeline: no ffmpeg/demucs/network needed,
    just exercises the web app's run-tracking and media-serving wiring.
    """
    on_progress = kwargs.get("on_progress")
    if on_progress:
        on_progress("separating")
        on_progress("aligning")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "clips_only.mp4").write_bytes(b"fake video")
    stems_dir = out_dir / "stems"
    stems_dir.mkdir(parents=True, exist_ok=True)
    (stems_dir / "vocals.wav").write_bytes(b"fake vocals")
    (stems_dir / "no_vocals.wav").write_bytes(b"fake instrumental")
    return out_dir / "clips_only.mp4"


def _wait_for_status(client, run_url, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"{run_url}/status.json")
        data = resp.get_json()
        if data["status"] in ("done", "error"):
            return data
        time.sleep(0.02)
    raise AssertionError("run did not finish in time")


def test_full_upload_and_export_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp_module, "run_pipeline", _fake_run_pipeline)

    app = webapp_module.create_app(tmp_path / "runs")
    client = app.test_client()

    assert client.get("/").status_code == 200

    data = {
        "title": "test song",
        "lyrics": "hello world",
        "song": (io.BytesIO(b"fake mp3 bytes"), "song.mp3"),
    }
    resp = client.post("/runs", data=data, content_type="multipart/form-data")
    assert resp.status_code == 302
    run_url = resp.headers["Location"]

    status = _wait_for_status(client, run_url)
    assert status["status"] == "done", status

    assert client.get(run_url).status_code == 200
    assert client.get(f"{run_url}/media/clips").status_code == 200
    assert client.get(f"{run_url}/media/vocals").status_code == 200
    assert client.get(f"{run_url}/media/nonsense").status_code == 404

    export_resp = client.post(
        f"{run_url}/export",
        json={"vocals": 1.0, "instrumental": 0.5, "clips": 1.2},
    )
    # render_mix needs real ffmpeg, which isn't installed in this test env;
    # the route should still respond with a clean JSON error, not crash.
    assert export_resp.status_code == 500
    assert "ffmpeg" in export_resp.get_json()["error"]


def test_rejects_missing_song(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp_module, "run_pipeline", _fake_run_pipeline)
    app = webapp_module.create_app(tmp_path / "runs")
    client = app.test_client()
    resp = client.post("/runs", data={"lyrics": "hello"}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_rejects_missing_lyrics(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp_module, "run_pipeline", _fake_run_pipeline)
    app = webapp_module.create_app(tmp_path / "runs")
    client = app.test_client()
    data = {"song": (io.BytesIO(b"fake mp3 bytes"), "song.mp3")}
    resp = client.post("/runs", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_rejects_unsupported_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp_module, "run_pipeline", _fake_run_pipeline)
    app = webapp_module.create_app(tmp_path / "runs")
    client = app.test_client()
    data = {
        "lyrics": "hello",
        "song": (io.BytesIO(b"not audio"), "song.exe"),
    }
    resp = client.post("/runs", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_discovers_existing_runs_on_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp_module, "run_pipeline", _fake_run_pipeline)
    work_root = tmp_path / "runs"
    output_dir = work_root / "abc123" / "output"
    output_dir.mkdir(parents=True)
    (output_dir / "clips_only.mp4").write_bytes(b"fake video")

    app = webapp_module.create_app(work_root)
    resp = app.test_client().get("/runs/abc123")
    assert resp.status_code == 200
