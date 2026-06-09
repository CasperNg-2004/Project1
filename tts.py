"""
tts.py — pyttsx3 text-to-speech

Uses a single persistent worker thread for all speech.
pyttsx3's Windows SAPI5 driver silently stops working on the second
runAndWait() call when the same engine instance is reused — reinitialising
the engine for every utterance is the only reliable fix on Windows.
"""

import logging
import queue
import threading
import pyttsx3

logger = logging.getLogger(__name__)

_SHUTDOWN = object()   # sentinel: gracefully shut down the worker thread


class TextToSpeech:
    def __init__(self, rate: int = 175, volume: float = 1.0):
        self._rate      = rate
        self._volume    = volume
        self._voice_id: str | None = None
        self._q: queue.Queue = queue.Queue()
        self._skip      = threading.Event()   # set → skip queued item
        self._cur_engine = None               # engine currently speaking (worker-owned)

        self._worker = threading.Thread(target=self._loop, daemon=True,
                                        name="tts-worker")
        self._worker.start()

    # ── worker ─────────────────────────────────────────────────────────────

    def _loop(self):
        """
        Runs forever in its own thread.
        A FRESH pyttsx3 engine is created for every utterance because the
        Windows SAPI5 driver does not reliably survive multiple runAndWait()
        calls on the same engine object.
        """
        while True:
            item = self._q.get()
            if item is _SHUTDOWN:
                logger.debug("TTS worker: shutdown signal received")
                break

            text, on_done = item

            # skip() was called while this item was queued
            if self._skip.is_set():
                logger.debug("TTS worker: skipping item (stop requested)")
                if on_done:
                    on_done()
                continue

            logger.debug("TTS worker: speaking %d chars", len(text))
            engine = None
            try:
                # Fresh engine every time — this is intentional (see module docstring)
                engine = pyttsx3.init()
                engine.setProperty("rate",   self._rate)
                engine.setProperty("volume", self._volume)
                if self._voice_id:
                    engine.setProperty("voice", self._voice_id)

                self._cur_engine = engine
                engine.say(text)
                engine.runAndWait()
                logger.debug("TTS worker: finished utterance")
            except Exception:
                logger.exception("pyttsx3 error during speech")
            finally:
                self._cur_engine = None
                if on_done:
                    on_done()

    # ── public API ─────────────────────────────────────────────────────────

    def set_voice(self, voice_id: str):
        """Set the voice to use for subsequent speak() calls."""
        self._voice_id = voice_id

    def list_voices(self):
        """Return available voices (creates a temporary engine — safe from any thread)."""
        tmp = pyttsx3.init()
        voices = tmp.getProperty("voices")
        tmp.stop()
        return voices

    def speak(self, text: str, on_done=None):
        """Queue text for playback. Returns immediately; on_done() called when done."""
        if not text:
            if on_done:
                on_done()
            return
        self._skip.clear()
        self._q.put((text, on_done))

    def stop(self):
        """Interrupt current speech and discard any queued items."""
        self._skip.set()

        # Drain the queue so nothing pending plays after stop
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

        # Interrupt the currently-playing utterance if any
        eng = self._cur_engine
        if eng is not None:
            try:
                eng.stop()
            except Exception:
                logger.debug("engine.stop() raised during stop()", exc_info=True)

        self._skip.clear()   # re-arm so next speak() works

    def close(self):
        """Shut down the worker thread gracefully."""
        self._q.put(_SHUTDOWN)
        self._worker.join(timeout=5)