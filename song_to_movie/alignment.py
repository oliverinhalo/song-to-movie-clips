from __future__ import annotations

import re
from pathlib import Path
from typing import List

from .models import AlignedWord

_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def tokenize_lyrics(text: str) -> List[str]:
    """Split raw lyric text into the word tokens used for alignment."""
    return _WORD_RE.findall(text)


def even_split_alignment(words: List[str], total_duration: float) -> List[AlignedWord]:
    """A dependency-free fallback aligner.

    Distributes `total_duration` across `words` proportionally to each
    word's character length. This is not accurate lip-sync-grade timing,
    but it is enough to smoke-test the rest of the pipeline (timeline
    building, clip fetching, assembly, mixing) without installing
    torch/torchaudio, and as a fallback if forced alignment fails.
    """
    if not words:
        return []
    weights = [max(1, len(w)) for w in words]
    total_weight = sum(weights)
    aligned: List[AlignedWord] = []
    t = 0.0
    for word, weight in zip(words, weights):
        duration = total_duration * (weight / total_weight)
        aligned.append(AlignedWord(text=word, start=t, end=t + duration))
        t += duration
    return aligned


def forced_align(vocals_path: Path, words: List[str]) -> List[AlignedWord]:
    """Word-level forced alignment of `words` against the audio at `vocals_path`.

    Uses torchaudio's CTC-based multilingual forced aligner
    (`torchaudio.pipelines.MMS_FA`), which takes a known transcript and the
    audio it was spoken/sung over and returns per-word start/end times -
    exactly the "forced alignment" task this needs, as opposed to open
    vocabulary speech recognition. Requires the optional `torch` and
    `torchaudio` dependencies (`pip install -e ".[alignment]"`).
    """
    try:
        import torch
        import torchaudio
        from torchaudio.pipelines import MMS_FA as bundle
    except ImportError as exc:
        raise RuntimeError(
            "forced_align requires torch and torchaudio "
            "(pip install -e \".[alignment]\"), or pass "
            "--no-forced-alignment to use the dependency-free fallback."
        ) from exc

    if not words:
        return []

    model = bundle.get_model()
    tokenizer = bundle.get_tokenizer()
    aligner = bundle.get_aligner()

    waveform, sample_rate = torchaudio.load(str(vocals_path))
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if sample_rate != bundle.sample_rate:
        waveform = torchaudio.functional.resample(waveform, sample_rate, bundle.sample_rate)

    normalized = [w.lower() for w in words]
    with torch.inference_mode():
        emission, _ = model(waveform)
        token_spans = aligner(emission[0], tokenizer(normalized))

    num_frames = emission.shape[1]
    audio_duration = waveform.shape[1] / bundle.sample_rate
    seconds_per_frame = audio_duration / num_frames

    aligned: List[AlignedWord] = []
    for word, spans in zip(words, token_spans):
        start = spans[0].start * seconds_per_frame
        end = spans[-1].end * seconds_per_frame
        aligned.append(AlignedWord(text=word, start=start, end=end))
    return aligned
