"""
stt.py — Vosk speech-to-text

Downloads the small English model on first run (~50 MB).
Call listen() to record until the stop_event is set and return the full transcript.
"""

import json
import logging
import os
import queue
import threading
import urllib.request
import zipfile

import pyaudio
from vosk import KaldiRecognizer, Model

logger = logging.getLogger(__name__)

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_DIR = os.path.join(os.path.dirname(__file__), "vosk-model-small-en-us-0.15")
MODEL_ZIP = os.path.join(os.path.dirname(__file__), "vosk-model.zip")

SAMPLE_RATE = 16000
CHUNK = 4096


def _ensure_model(progress_cb=None):
    """Download and unzip the Vosk model if it isn't already present."""
    if os.path.isdir(MODEL_DIR):
        return

    if progress_cb:
        progress_cb("Downloading Vosk model (~50 MB) — one-time setup…")

    def _report(block, block_size, total):
        if progress_cb and total > 0:
            pct = min(100, int(block * block_size * 100 / total))
            progress_cb(f"Downloading Vosk model… {pct}%")

    urllib.request.urlretrieve(MODEL_URL, MODEL_ZIP, reporthook=_report)

    if progress_cb:
        progress_cb("Extracting model…")
    with zipfile.ZipFile(MODEL_ZIP, "r") as zf:
        zf.extractall(os.path.dirname(__file__))
    os.remove(MODEL_ZIP)


class SpeechToText:
    def __init__(self, progress_cb=None):
        _ensure_model(progress_cb)
        self._model = Model(MODEL_DIR)
        self._recognizer = KaldiRecognizer(self._model, SAMPLE_RATE)
        self._audio = pyaudio.PyAudio()

    def listen(self, on_partial=None, stop_event: threading.Event = None) -> str:
        """
        Record audio from the mic, accumulating all finalized utterances
        until stop_event is set or silence ends the session.

        Args:
            on_partial: optional callback(str) called with partial transcripts.
            stop_event: optional threading.Event; set it to stop recording.

        Returns:
            Full transcript string of everything spoken (may be empty).
        """
        stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )

        parts: list[str] = []
        try:
            while True:
                if stop_event and stop_event.is_set():
                    # Flush any remaining audio before exiting
                    final = json.loads(self._recognizer.FinalResult())
                    text = final.get("text", "").strip()
                    if text:
                        parts.append(text)
                    break
                data = stream.read(CHUNK, exception_on_overflow=False)
                if self._recognizer.AcceptWaveform(data):
                    res = json.loads(self._recognizer.Result())
                    text = res.get("text", "").strip()
                    if text:
                        parts.append(text)
                        logger.debug("STT utterance: %s", text)
                else:
                    if on_partial:
                        partial = json.loads(self._recognizer.PartialResult())
                        on_partial(partial.get("partial", ""))
        finally:
            stream.stop_stream()
            stream.close()
            self._recognizer = KaldiRecognizer(self._model, SAMPLE_RATE)  # reset

        return " ".join(parts)

    def close(self):
        self._audio.terminate()