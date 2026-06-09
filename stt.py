"""
stt.py — Vosk speech-to-text

Downloads the small English model on first run (~50 MB).
Call listen() to record one utterance and return the transcript string.
"""

import json
import os
import queue
import threading
import urllib.request
import zipfile

import pyaudio
from vosk import KaldiRecognizer, Model

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
        self._stop_event = threading.Event()

    def listen(self, on_partial=None, stop_event: threading.Event = None) -> str:
        """
        Record audio from the mic until silence is detected.

        Args:
            on_partial: optional callback(str) called with partial transcripts.
            stop_event: optional threading.Event; set it to abort early.

        Returns:
            Final transcript string (may be empty).
        """
        stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )

        result_text = ""
        try:
            while True:
                if stop_event and stop_event.is_set():
                    break
                data = stream.read(CHUNK, exception_on_overflow=False)
                if self._recognizer.AcceptWaveform(data):
                    res = json.loads(self._recognizer.Result())
                    result_text = res.get("text", "")
                    if result_text:
                        break
                else:
                    if on_partial:
                        partial = json.loads(self._recognizer.PartialResult())
                        on_partial(partial.get("partial", ""))
        finally:
            stream.stop_stream()
            stream.close()
            self._recognizer = KaldiRecognizer(self._model, SAMPLE_RATE)  # reset

        return result_text.strip()

    def close(self):
        self._audio.terminate()