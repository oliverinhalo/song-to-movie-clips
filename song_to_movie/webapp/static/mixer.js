const clips = document.getElementById("clips");
const vocals = document.getElementById("vocals");
const instrumental = document.getElementById("instrumental");
const tracks = [clips, vocals, instrumental];

function bindVolume(sliderId, media) {
  const slider = document.getElementById(sliderId);
  const apply = () => {
    // HTMLMediaElement.volume throws outside [0, 1]; sliders above 1x only
    // take effect in the exported file, via ffmpeg's volume filter.
    media.volume = Math.min(1, Math.max(0, Number(slider.value)));
  };
  apply();
  slider.addEventListener("input", apply);
}
bindVolume("clips-vol", clips);
bindVolume("vocals-vol", vocals);
bindVolume("instrumental-vol", instrumental);

function playAll() {
  tracks.forEach((t) => {
    t.currentTime = clips.currentTime;
  });
  tracks.forEach((t) => t.play());
}
function pauseAll() {
  tracks.forEach((t) => t.pause());
}
document.getElementById("play").addEventListener("click", playAll);
document.getElementById("pause").addEventListener("click", pauseAll);

document.getElementById("export").addEventListener("click", async () => {
  const status = document.getElementById("status");
  status.textContent = "Rendering final mix...";
  const body = {
    clips: document.getElementById("clips-vol").value,
    vocals: document.getElementById("vocals-vol").value,
    instrumental: document.getElementById("instrumental-vol").value,
  };
  try {
    const res = await fetch("/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    status.textContent = res.ok ? `Saved to ${data.path}` : `Error: ${JSON.stringify(data)}`;
  } catch (err) {
    status.textContent = `Export failed: ${err}`;
  }
});
