import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info("Caricamento modello Whisper small (~465MB, solo prima volta)...")
        _model = WhisperModel("small", device="cpu", compute_type="int8")
        logger.info("Modello Whisper caricato")
    return _model


def transcribe(audio_path: str) -> str:
    model = _get_model()
    segments, info = model.transcribe(
        audio_path,
        language="it",
        beam_size=5,
        vad_filter=True,          # ignora i silenzi
        initial_prompt="Messaggio vocale in italiano.",
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    logger.info(f"Trascritto ({info.language}, {info.duration:.1f}s): {text[:80]}")
    return text
